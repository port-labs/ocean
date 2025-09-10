# Port Ocean – GitHub Integration (Async)

An async GitHub → Port Ocean integration that ingests **Repositories**, **Pull Requests**, **Issues**, and **Files** (with glob filters). It handles GitHub rate limits, supports optional webhooks, and provides configurable ingestion.

## Features
- Async HTTP via Ocean’s client
- Rate limit handling (Retry-After, reset headers, secondary RL backoff)
- Filters: PR state (`open|closed|all|merged`) & updated-since days; Issues by state; file globs/branch
- File content capping & preview to avoid oversized payloads
- Optional webhook endpoint with HMAC verification
- Verbose logging & sensible batching
- Sample blueprints, views, dashboards

## Requirements
- Python 3.10+
- Port workspace
- GitHub token with read access (`repo` for private)

## Local Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

export OCEAN__INTEGRATION__SECRETS__GITHUB_TOKEN="ghp_..."
# optional
export OCEAN__INTEGRATION__SECRETS__GITHUB_WEBHOOK_SECRET="topsecret"

ocean sail