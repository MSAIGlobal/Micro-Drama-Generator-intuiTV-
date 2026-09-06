import asyncio
import hmac
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipelines.idea2video import Idea2VideoPipeline
from pipelines.script2video import Script2VideoPipeline
from agents.character_extractor import CharacterExtractor


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="MicroDrama AI API", version="1.0.0")

# CORS: explicit allow-list from env (comma-separated). No wildcard — a "*"
# origin with credentials is invalid and unsafe. Empty = no cross-origin access.
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("MICRODRAMA_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Optional bearer token: when MICRODRAMA_API_TOKEN is set, the job endpoints
# require it (constant-time check); left unset the API stays open for local dev.
API_TOKEN = os.environ.get("MICRODRAMA_API_TOKEN", "")


def require_auth(authorization: Optional[str] = Header(None)) -> None:
    if not API_TOKEN:
        return
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {API_TOKEN}"):
        raise HTTPException(status_code=401, detail="unauthorized")

# Ensure outputs directory exists on startup
OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(exist_ok=True)

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------
# job structure:
# {
#   "status": "running" | "completed" | "failed",
#   "events": [...],           # list of JSON-serialisable dicts
#   "video_url": str | None,
#   "error": str | None,
#   "queue": asyncio.Queue,    # fed by pipeline, consumed by SSE
# }
jobs: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class GenerateRequest(BaseModel):
    # Bounded lengths guard against cost/DoS via oversized LLM/video inputs.
    idea: str = Field(..., max_length=4000)
    user_requirement: str = Field("", max_length=4000)
    style: str = Field("Cinematic", max_length=64)
    mode: str = Field("idea2video", max_length=32)  # "idea2video" or "script2video"
    script: str = Field("", max_length=20000)       # used when mode == "script2video"


class GenerateResponse(BaseModel):
    job_id: str


class JobResult(BaseModel):
    job_id: str
    status: str
    video_url: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Background pipeline runner
# ---------------------------------------------------------------------------
async def run_pipeline(job_id: str, req: GenerateRequest) -> None:
    job = jobs[job_id]
    queue: asyncio.Queue = job["queue"]

    async def progress_callback(stage: str, message: str, progress: int) -> None:
        event = {
            "type": "progress",
            "stage": stage,
            "message": message,
            "progress": progress,
        }
        job["events"].append(event)
        await queue.put(event)

    try:
        if req.mode == "script2video":
            # Script2Video: user provides a single scene script
            script_pipeline = Script2VideoPipeline()
            character_extractor = CharacterExtractor()

            await progress_callback("characters", "Extracting characters...", 10)
            characters = await character_extractor.extract_characters(req.script or req.idea)

            output_dir = str(OUTPUTS_DIR / job_id / "scene_00")
            video_path = await script_pipeline.run(
                script=req.script or req.idea,
                characters=characters,
                user_requirement=req.user_requirement,
                style=req.style,
                working_dir=output_dir,
                progress_callback=progress_callback,
                scene_idx=0,
                base_progress=15,
                progress_range=80,
            )
        else:
            # Idea2Video: full agentic pipeline
            idea_pipeline = Idea2VideoPipeline()
            video_path = await idea_pipeline.run(
                idea=req.idea,
                user_requirement=req.user_requirement,
                style=req.style,
                job_id=job_id,
                progress_callback=progress_callback,
            )

        # Convert local path to URL
        rel_path = Path(video_path).relative_to(Path("."))
        video_url = f"/{rel_path}"

        job["status"] = "completed"
        job["video_url"] = video_url

        complete_event = {
            "type": "complete",
            "video_url": video_url,
            "progress": 100,
        }
        job["events"].append(complete_event)
        await queue.put(complete_event)

    except Exception as exc:
        error_msg = str(exc)
        job["status"] = "failed"
        job["error"] = error_msg

        error_event = {
            "type": "error",
            "message": error_msg,
            "progress": -1,
        }
        job["events"].append(error_event)
        await queue.put(error_event)

    finally:
        # Signal SSE consumers that the stream is done
        await queue.put(None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "microdrama-api"}


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
):
    require_auth(authorization)
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "running",
        "events": [],
        "video_url": None,
        "error": None,
        "queue": asyncio.Queue(),
    }
    background_tasks.add_task(run_pipeline, job_id, req)
    return GenerateResponse(job_id=job_id)


@app.get("/api/status/{job_id}")
async def status_stream(job_id: str):
    """SSE endpoint — streams progress events until job completes or fails."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    async def event_generator():
        # Replay already-emitted events first (in case client reconnects)
        for event in job["events"]:
            yield f"data: {json.dumps(event)}\n\n"

        # If job is already done, we've replayed everything — finish
        if job["status"] in ("completed", "failed"):
            return

        # Otherwise stream live events from queue
        queue: asyncio.Queue = job["queue"]
        while True:
            event = await queue.get()
            if event is None:
                # Sentinel — pipeline finished
                break
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in ("complete", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/result/{job_id}", response_model=JobResult)
async def get_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobResult(
        job_id=job_id,
        status=job["status"],
        video_url=job.get("video_url"),
        error=job.get("error"),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    # reload defaults OFF (production-safe); enable locally with MICRODRAMA_RELOAD=1.
    reload = os.environ.get("MICRODRAMA_RELOAD", "0") == "1"
    host = os.environ.get("MICRODRAMA_HOST", "127.0.0.1")
    port = int(os.environ.get("MICRODRAMA_PORT", "8000"))
    uvicorn.run("api:app", host=host, port=port, reload=reload)
