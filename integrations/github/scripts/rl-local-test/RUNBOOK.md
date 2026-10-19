# Centralized rate limiter — local 4-pod runbook (short)

**Full step-by-step detail:** [LOCAL_RUNBOOK.md](./LOCAL_RUNBOOK.md) (Redis, ocean-gateway, ngrok, env files, scenarios A–D).

Narrow the Port integration mapping to **one repo** and **pull_request** (and action kinds if testing actions) before running.

## Prerequisites (once)

1. Redis on `localhost:6379` (`brew services start redis` or Docker — see LOCAL_RUNBOOK).
2. Fill placeholders in `env.full`, `env.incremental`, `env.live`, `env.actions`; per terminal: `cp scripts/rl-local-test/env.<pod> .env`.
3. Port prod API creds + integration id; live pod: **ocean-gateway** + **ngrok → :8080** (not Ocean HTTP).

## Run A — centralized ON (main test)

1. **Pre-burn GitHub quota** (optional script): `GET /rate_limit`, then repeated `GET .../pulls?per_page=1` until `remaining` ~50–100; stop before hard block.
2. **Seed data — full**: run your PR bulk-create script (many PRs in test repo).
3. **Start pods** (four terminals, `cd integrations/github`):
   - `cp scripts/rl-local-test/env.full .env && ocean sail`
   - `cp scripts/rl-local-test/env.incremental .env && ocean sail`
   - `cp scripts/rl-local-test/env.live .env && ocean sail`
   - `cp scripts/rl-local-test/env.actions .env && ocean sail`
4. **Within ~2 min of full pod starting resync**: seed **live** — create 1–2 PRs (small script); trigger a **Port action** (e.g. PR comment) for actions pod.
5. Let all pods run until full hammer finishes or you see sustained `Centralized rate limiter blocked request` across tiers.
6. Save logs from all terminals; grep for:
   - `Centralized rate limiter blocked request`
   - `Centralized rate limiter recorded response`
   - `GitHub centralized rate limit state`
   - `rate limit exhausted` / `Requests paused`
   - `[sync_tier=`

## Run B — centralized OFF (baseline local limiter + jitter)

1. Set `OCEAN__CENTRALIZED_RATE_LIMITER__ENABLED=false` in all four env files (or override in shell).
2. Repeat Run A steps 1–6 with same seed timing.
3. Compare wall time, 429/403 counts, and local limiter sleep logs vs Run A.

## Run C — fail-open (edge)

1. Restore `CENTRALIZED_RATE_LIMITER__ENABLED=true`.
2. Start full + incremental pods; after traffic starts, `docker stop` Redis (or block port).
3. Confirm logs: `acquire failed (Redis unavailable); allowing request` and no crash; stop pods.

## Run D — local limiter unchanged (regression)

1. Centralized OFF; single **full** pod only.
2. Confirm same `on_response` / semaphore / `Requests paused` behavior as pre-feature branch (no centralized log lines).

## After validation

Remove `TODO(rl-local-test)` log blocks in `port_ocean/rate_limiting/utils.py` and `rate_limit_wrapper.py`.
