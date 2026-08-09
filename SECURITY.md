# Security Policy

Media Stream AI Limited (Company No. 16249524) treats the security of this
repository and the systems it deploys as a first-order engineering concern.
This policy supports our Cyber Essentials posture and the MSAI AI Act
engineering programme (MSAI-ENG-AIACT-001).

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Report suspected vulnerabilities privately to **security@mediastreamai.com**.
Please include:

- a description of the issue and its potential impact;
- steps to reproduce or a proof of concept;
- affected component, version, commit or deployment.

We aim to acknowledge reports within **2 business days** and to provide a
remediation plan or status within **10 business days**. Please give us a
reasonable opportunity to remediate before any public disclosure.

You may also use GitHub **private vulnerability reporting** (Security tab →
"Report a vulnerability") where enabled.

## Supported versions

Security fixes are applied to the default branch and the current production
deployment. Older branches are not maintained.

## Our controls

This repository ships an automated security baseline:

- **CodeQL** static analysis (`.github/workflows/codeql.yml`).
- **Semgrep + gitleaks** portable security gate on every push and pull
  request (`.github/workflows/security-scan.yml`).
- **Dependabot** automated dependency and GitHub Actions updates
  (`.github/dependabot.yml`).
- Secret files are excluded from version control; see
  `docs/security/cyber-essentials.md` for the full control mapping and
  `docs/security/secret-remediation-runbook.md` for incident handling.

## Scope

Please act in good faith, avoid privacy violations and service disruption,
and only test against assets you are authorised to test.
