# Centralized rate limiter — local runbook (full detail)

Local testing for **centralized Redis rate limiting** on the GitHub integration: multiple Ocean processes, **prod Port API**, **local Redis**, optional **ocean-gateway** + **ngrok** for live events.

**Branch:** feature work on `task_tmflxm/centralized_rate_limiter_for_ocean_core_changes` (Ocean core + GitHub `GitHubRateLimitWrapper`).

---

## 1. Architecture

### 1.1 Centralized rate limiter (all GitHub HTTP pods)

- **Ocean core:** `RetryConfig.rate_limiter` → `acquire()` / `record_rate_limit_response()` on each retry attempt.
- **Redis keys:** `ratelimit:{org_id}:{integration_identifier}:{pool}` (pools: `rest`, `graphql`).
- **Sync tier** (from pod config, not from “what job is running”):
  - Full resync pod → `LOW`
  - `OCEAN__INTEGRATION__INCREMENTAL_SYNC_ENABLED=true` → `MEDIUM`
  - Live events / webhooks pod → `HIGH`
  - Actions-only pod → `HIGH`

All competing pods must share:

- `OCEAN__INTEGRATION__IDENTIFIER` (same installation)
- Same GitHub token/org (same GitHub rate limit bucket)
- `OCEAN__CENTRALIZED_RATE_LIMITER__REDIS__URL` → **same Redis**

### 1.2 Live events (optional pod)

Prod Port API does **not** push webhooks to your laptop. Local live-events use:

```text
GitHub → ngrok → ocean-gateway (:8080) → XADD Redis stream
       → Ocean (WEBHOOKS_ONLY, Redis consumer) → GitHub API
```

- **ocean-gateway** repo: [port-labs/ocean-gateway](https://github.com/port-labs/ocean-gateway)
- **Not** started by Port devbox — run `go run ./cmd/gateway` yourself.
- Pick a **`liveEventsUUID`** (e.g. `rl-local-github`) and use it in:
  - GitHub webhook URL
  - `OCEAN__BASE_URL` on the live Ocean pod
- Stream key: `{liveEventsUUID}/live-events/raw/event-stream`
- GitHub processor path: `/webhook` → gateway URL suffix: `/integration/webhook`

Full URL pattern:

```text
https://<ngrok-host>/live-events/<liveEventsUUID>/integration/webhook
```

### 1.3 What Port devbox gives you

- **redis-db** on `6379` if you use Port docker compose (optional).
- **Does not** run ocean-gateway or Ocean.

---

## 2. Prerequisites (one-time)

### 2.1 Code

- Ocean repo on the rate-limiter feature branch.
- GitHub integration wired with `GitHubRateLimitWrapper` + `RetryConfig.rate_limiter`.
- Optional: clone `ocean-gateway` next to `ocean`.

### 2.2 Port (prod API)

- Integration exists in prod (or your target Port env).
- `OCEAN__PORT__BASE_URL=https://api.getport.io` (or your org URL).
- `OCEAN__PORT__CLIENT_ID` / `OCEAN__PORT__CLIENT_SECRET`.
- Narrow **mapping** for tests: **one repo**, **pull_request** (add action kinds if testing actions).

### 2.3 GitHub

- PAT or GitHub App token with access to the test org/repo.
- `OCEAN__INTEGRATION__CONFIG__GITHUB_TOKEN`, `GITHUB_ORGANIZATION`, `WEBHOOK_SECRET`.

### 2.4 Env templates

Edit all files under `integrations/github/scripts/rl-local-test/`:

| File | Role |
|------|------|
| `env.full` | POLLING, full resync, tier LOW, PR list hammer on full resync |
| `env.incremental` | POLLING + incremental flag, tier MEDIUM |
| `env.live` | WEBHOOKS_ONLY + live-events Redis consumer, tier HIGH |
| `env.actions` | ACTIONS_ONLY, tier HIGH |

**Same on every file:**

- `OCEAN__INTEGRATION__IDENTIFIER` (must match across all pods you run together)
- GitHub + Port credentials

Ocean loads **`.env`** from `integrations/github/` (cwd when you `ocean sail`). Templates are not loaded automatically — **copy** the right template to `.env` per terminal (see §4).

### 2.5 Temporary debug logs

While validating, branch includes `TODO(rl-local-test)` **INFO** logs in:

- `port_ocean/rate_limiting/utils.py`
- `integrations/github/github/clients/rate_limiter/rate_limit_wrapper.py`

Remove after test runs (see §8).

---

## 3. Infrastructure commands

### 3.1 Redis (required)

**Homebrew (no Docker):**

```bash
brew install redis
brew services start redis    # background
# OR: redis-server           # foreground in its own terminal
redis-cli ping               # expect PONG
```

**Docker (alternative):**

```bash
docker run -d --name ocean-rl-redis -p 6379:6379 redis:7-alpine
docker exec ocean-rl-redis redis-cli ping
```

**If PONG fails:** `lsof -i :6379` — Port devbox `redis-db` may already own 6379; use it instead of starting a second Redis.

**Env (all pods that use centralized RL):**

```bash
OCEAN__CENTRALIZED_RATE_LIMITER__ENABLED=true
OCEAN__CENTRALIZED_RATE_LIMITER__REDIS__URL=redis://localhost:6379
```

Optional Redis settings (local defaults usually enough):

```bash
# OCEAN__CENTRALIZED_RATE_LIMITER__REDIS__PASSWORD=
# OCEAN__CENTRALIZED_RATE_LIMITER__REDIS__USERNAME=
# OCEAN__CENTRALIZED_RATE_LIMITER__REDIS__ENABLE_TLS=false
```

Live-events consumer (live pod only) — **same Redis instance:**

```bash
OCEAN__LIVE_EVENTS__IS_REDIS_STREAM_CONSUMER_ENABLED=true
OCEAN__LIVE_EVENTS__REDIS__URL=redis://localhost:6379
```

### 3.2 ocean-gateway (live-events only)

Terminal dedicated to gateway:

```bash
cd /path/to/ocean-gateway
export REDIS_LIVE_EVENTS_URL=localhost:6379
export LISTEN_ADDR=:8080
go run ./cmd/gateway
```

Expect logs: `redis connected`, `gateway listening` `addr=:8080`.

Smoke:

```bash
curl -s http://localhost:8080/healthz | jq .
```

Gateway env reference:

| Variable | Default | Local test |
|----------|---------|------------|
| `LISTEN_ADDR` | `:8080` | `:8080` |
| `REDIS_LIVE_EVENTS_URL` | `localhost:6379` | `localhost:6379` |
| `METRICS_LISTEN_ADDR` | `:9100` | optional |

### 3.3 ngrok (live-events only)

Expose **gateway**, not Ocean:

```bash
ngrok http 8080
```

Use the `https://….ngrok-free.app` host in GitHub webhook URL and in `OCEAN__BASE_URL` (see §3.4).

### 3.4 Live pod `OCEAN__BASE_URL`

Must include `/live-events/<liveEventsUUID>/` so Ocean resolves the Redis stream.

Example (`liveEventsUUID` = `rl-local-github`, ngrok host = `abc.ngrok-free.app`):

```bash
OCEAN__BASE_URL=https://abc.ngrok-free.app/live-events/rl-local-github/integration/webhook
```

GitHub webhook **Payload URL** (same path):

```text
https://abc.ngrok-free.app/live-events/rl-local-github/integration/webhook
```

---

## 4. Running Ocean (per pod)

Working directory:

```bash
cd /Users/danamsalem/dev/ocean/integrations/github
```

**Per terminal:** copy template → `.env`, then sail:

```bash
cp scripts/rl-local-test/env.full .env          # change per pod
# edit .env if needed (ngrok host, uuid, secrets)

/Users/danamsalem/dev/ocean/.venv/bin/ocean sail
# OR: ocean sail  if on PATH
```

Capture logs:

```bash
cp scripts/rl-local-test/env.full .env && ocean sail 2>&1 | tee /tmp/ocean-rl-full.log
```

**Startup checks (centralized ON):**

```text
Centralized rate limiter enabled with Redis
```

If you see Redis connection failure → no-op limiter; fix Redis before measuring.

| Terminal | `cp` source | Sync tier | Notes |
|----------|-------------|-----------|--------|
| 1 | `env.full` | LOW | PR hammer on full resync (`pull_request_exporter`) |
| 2 | `env.incremental` | MEDIUM | `INCREMENTAL_SYNC_ENABLED=true` |
| 3 | `env.live` | HIGH | Needs gateway + ngrok + GitHub webhook |
| 4 | `env.actions` | HIGH | Trigger Port action from UI |

**Ports:** gateway `8080`, Ocean often `8000`, Redis `6379` — avoid clashes.

---

## 5. Live-events-only shortcut

If you only care about **live → GitHub API → rate limits** (no full/incremental/actions):

1. Redis (§3.1)
2. ocean-gateway (§3.2)
3. ngrok → 8080 (§3.3)
4. One Ocean: `cp scripts/rl-local-test/env.live .env`, set `OCEAN__BASE_URL` + uuid (§3.4)
5. GitHub webhook → gateway URL
6. Trigger PR events (open/edit/close or redeliver)

**Pipeline smoke without GitHub:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST "http://localhost:8080/live-events/rl-local-github/integration/webhook" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -d '{"zen":"test"}'
```

Expect `202`. Then check Ocean logs and:

```bash
redis-cli XLEN rl-local-github/live-events/raw/event-stream
```

---

## 6. Test scenarios

### 6.1 Run A — Centralized ON (main)

**Goal:** Multi-pod contention + centralized admission; compare logs to Run B.

1. Ensure `OCEAN__CENTRALIZED_RATE_LIMITER__ENABLED=true` in all env templates (or `.env` copies).
2. Start Redis (§3.1).
3. **(Optional)** Pre-burn GitHub quota: `curl -H "Authorization: Bearer $TOKEN" https://api.github.com/rate_limit`, then repeated cheap `GET .../pulls?per_page=1` until `remaining` ~50–100 (stop before hard block).
4. **Seed:** bulk-create PRs in test repo (full pod load).
5. **Live stack** (if using live pod): gateway + ngrok + webhook URL (§3.2–3.4).
6. Start Ocean pods (§4) — four terminals or subset (minimum: **full** for hammer; add **live** for HIGH tier).
7. Within ~1–2 min of full resync starting:
   - Create 1–2 PRs for live traffic.
   - Fire a Port **action** (e.g. PR comment) if actions pod is running.
8. Run until full PR hammer completes or logs show sustained centralized blocks.
9. Save logs; grep (§7).

### 6.2 Run B — Centralized OFF (baseline)

1. Set `OCEAN__CENTRALIZED_RATE_LIMITER__ENABLED=false` in all templates or `.env` files.
2. Repeat Run A (same seed timing).
3. Expect **no** `Centralized rate limiter *` lines; local `Requests paused`, `[sync_tier=…]` jitter still present.

### 6.3 Run C — Fail-open (edge)

1. `CENTRALIZED_RATE_LIMITER__ENABLED=true`.
2. Start **full** + **incremental** only.
3. After traffic starts: stop Redis (`brew services stop redis` or `docker stop ocean-rl-redis`).
4. Expect: `Centralized rate limiter acquire failed (Redis unavailable); allowing request` — no crash.
5. Restart Redis before next run.

### 6.4 Run D — Local limiter regression

1. `CENTRALIZED_RATE_LIMITER__ENABLED=false`.
2. **Only** full pod: `cp env.full .env` + `ocean sail`.
3. Confirm local limiter behavior unchanged; no centralized log lines.

---

## 7. Log analysis

Save terminal output or use `tee` under `/tmp/ocean-rl-*.log`.

**Grep:**

```bash
grep -E "Centralized rate limiter|GitHub centralized|rate limit exhausted|Requests paused|sync_tier=" /tmp/ocean-rl-*.log
```

| Question | What to look for |
|----------|------------------|
| Centralized working | `Centralized rate limiter enabled with Redis`; `blocked request` with `pool`, `tier`, `wait_seconds`; `recorded response` |
| GitHub publish | `GitHub centralized rate limit state` |
| Local limiter | `Requests paused`, `GitHub rate limit exhausted`, `on_response` warnings |
| Retry / jitter | `[sync_tier=…]` on retry lines |
| Fail-open | Redis down + acquire warnings, process continues |
| Compare A vs B | Wall time, 429/403 rate, sleep/block counts |

**Edge cases:** wrong `IDENTIFIER` across pods (no sharing); tier mismatch (incremental flag on wrong pod); live pod without gateway (empty stream); graphql vs `rest` pool.

---

## 8. Cleanup after validation

1. Stop Ocean processes, gateway, ngrok.
2. Stop Redis if you started it for the test.
3. Remove `TODO(rl-local-test)` log blocks in:
   - `port_ocean/rate_limiting/utils.py`
   - `integrations/github/github/clients/rate_limiter/rate_limit_wrapper.py`
4. Revert test GitHub webhook URL if you pointed a prod repo at ngrok.

---

## 9. Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| No centralized logs | `ENABLED=false`, Redis down, or startup used no-op limiter |
| Live pod idle | No gateway, wrong uuid in `OCEAN__BASE_URL`, or GitHub still pointing at prod URL |
| `LiveEventsUuidNotFoundError` | `OCEAN__BASE_URL` missing `/live-events/<uuid>/` |
| Gateway 202 but Ocean silent | Stream uuid mismatch; check `redis-cli KEYS '*live-events*'` |
| Port API errors | Credentials, integration id, or org blocked |
| `test_rate_limit_403` test failures | Separate unit-test mock issue; not required for manual run |

---

## 10. File index

```text
integrations/github/scripts/rl-local-test/
  LOCAL_RUNBOOK.md     ← this document
  RUNBOOK.md           ← short checklist
  env.full
  env.incremental
  env.live
  env.actions
  env.shared.example
```

**Related code:**

- Full resync PR hammer: `integrations/github/github/core/exporters/pull_request_exporter/core.py` (`_repeat_list_pulls_for_full_resync`)
- Gateway README: `ocean-gateway/README.md` (on-premises webhook URL section)
