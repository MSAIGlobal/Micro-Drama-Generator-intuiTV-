# Cyber Essentials — control mapping (Micro-Drama-Generator-intuiTV-)

_Last updated: 2026-08-09. Part of MSAI-ENG-AIACT-001 cross-platform security
hardening. Owner: AI Governance with Platform Engineering._

This document maps the automated controls in this repository to the five
Cyber Essentials technical controls. It is evidence, not aspiration: every
row points at a file or a GitHub setting that can be demonstrated.

## The five controls

### 1. Firewalls / boundary
Deployment boundary is enforced at the hosting layer (Netlify / Vercel /
GB10 node) and in MSAI Cloud Portal network policy, not in this repository.
Repository-side contribution: no secrets in source (below) so a boundary
breach does not hand over live credentials.

### 2. Secure configuration
- **Static analysis**: CodeQL (`.github/workflows/codeql.yml`) and Semgrep
  OSS (`.github/workflows/security-scan.yml`) run `security-audit`,
  `secrets` and `owasp-top-ten` rulesets. Detected languages: js, py.
- **HTTP security headers**: a non-breaking baseline (HSTS,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`,
  `Referrer-Policy`, `Cross-Origin-Opener-Policy`, a conservative
  `Permissions-Policy`) is set at the deployment layer where this repo
  serves web content (`netlify.toml` / `vercel.json` / `public/_headers`).
  A tuned `Content-Security-Policy` is the per-application follow-up: enable
  it in `Report-Only` first, review reports, then promote to enforcing.
- **No committed secrets**: `.env*` secret files are git-ignored;
  `.gitleaks.toml` + the gitleaks job block re-introduction.

### 3. Security update management
- **Dependabot** (`.github/dependabot.yml`) opens weekly grouped security
  updates for every package ecosystem in this repo plus GitHub Actions.
- **Dependency audit** job (`security-scan.yml`) surfaces known-vulnerable
  dependencies on every push (advisory during rollout, to be promoted to
  blocking once the backlog is cleared).

### 4. User access control
- Enforced through GitHub organisation membership, branch protection and
  least-privilege `GITHUB_TOKEN` permissions (`permissions:` blocks in all
  workflows are read-only by default).
- Recommended repo settings (configure in GitHub, tracked in the register):
  require pull-request review, require status checks (Security Scan) to
  pass, restrict who can push to the default branch, require signed commits.

### 5. Malware protection
- Supply-chain: Dependabot + dependency audit + Semgrep reduce the risk of
  malicious or vulnerable dependencies reaching production.
- Secret scanning (gitleaks) prevents credential leakage that malware could
  weaponise.

## Evidence

Workflow run logs (Actions tab), Dependabot alerts (Security tab) and this
file constitute the demonstrable evidence for the controls above. Where a
control is enforced in GitHub settings rather than in code, the setting is
recorded in the MSAI applicability register (MSAI-AIACT-REG-001).

## Known gaps (this repo)

See `docs/security/secret-remediation-runbook.md` if this repo previously
tracked a secret file. Rotation and git-history purge for any historical
exposure are tracked there and owned by Security with Operations.
