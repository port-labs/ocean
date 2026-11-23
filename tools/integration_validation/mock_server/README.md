# Integration validation mock server

Local FastAPI server that impersonates a 3rd-party API so an Ocean integration can run a full resync **without vendor credentials**. The validation runner (or a test) drives it via the admin API; the integration under test talks to it like a real vendor base URL.

Binds to `127.0.0.1` only.

## Who talks to what

```text
Runner / test                      Integration (ocean sail)
     |                                      |
     |  POST /__admin/scenario              |  GET/POST/... /api/...
     |  GET  /__admin/journal               |  (any path the vendor client uses)
     |  GET  /__admin/unmatched             |
     |  GET  /__admin/unused                |
     |  POST /__admin/reset                 |
     v                                      v
              Mock server (this package)
```

Two audiences hit the same process:

| Caller | Routes | When |
| --- | --- | --- |
| **Runner / tests** | `/__admin/*` | Before/after a scenario: load fixtures, inspect what was called, reset |
| **Integration** | Everything else (catch-all) | During resync: same paths/methods it would call on the real vendor |

Unmatched catch-all requests return **HTTP 599** and are journaled so missing fixtures show up as failures.

## Typical scenario lifecycle

1. **Start** the server with a fixture root (usually `integrations/<name>/validation/mock`).
2. **Load routes** — `POST /__admin/scenario` with route YAML paths relative to that root. Clears journal, call counts, and sequence counters.
3. **Run the integration** pointed at `http://127.0.0.1:<port>` (fake API keys). Each vendor HTTP call is matched and answered from the loaded routes.
4. **Inspect** — `GET /__admin/journal` (all requests), `/__admin/unmatched` (no fixture), `/__admin/unused` (loaded but never hit).
5. **Reset or reload** — `POST /__admin/reset` clears journal/counts/sequences while keeping routes; or load another scenario with step 2.

## Admin API (`/__admin`)

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/__admin/scenario` | Load route files and reset state. Body: `{"routes": ["routes/team.yaml", ...]}` (paths relative to `--fixture-root`). Returns `route_ids`. |
| `GET` | `/__admin/journal` | Every received catch-all request plus `matched_route_id` / `response_status`, and per-route `route_call_counts`. |
| `GET` | `/__admin/unmatched` | Journal entries with no matching route (`matched_route_id: null`). |
| `GET` | `/__admin/unused` | Loaded routes with `call_count: 0`. |
| `POST` | `/__admin/reset` | Clear journal, zero call counts, reset sequence counters. Routes stay loaded. |

Admin paths are **not** matched as mock routes; they are reserved for control/inspection.

## Catch-all mock requests

Any non-admin `GET` / `POST` / `PUT` / `PATCH` / `DELETE` / `HEAD` / `OPTIONS` path is treated as a vendor call:

1. Parse method, path, query, headers, body.
2. Find a matching loaded route (see below).
3. Render the response (inline `body`, `body_file`, or next step in a `sequence`).
4. Append a journal entry and bump that route's call count.

If nothing matches → **599** + `{"error": "unmatched_request", ...}`.

## Matching rules (short)

- Required: `method` + `path` (`path` may use `{param}` templates; captures feed `body_file` templates).
- Optional subset matchers: `query`, `headers`, `body` — listed keys must match; extra keys on the request are ignored.
- When several routes match, the **last** matching route in load order wins (put more specific routes after general ones).
- A route defines exactly one of `response` or `sequence` (ordered responses on successive hits; last step repeats).

## Fixture layout

`--fixture-root` is the filesystem root for scenario assets (not the whole validation suite). Typical layout:

```text
integrations/<name>/validation/mock/
  routes/
    team.yaml
  bodies/
    teams_page_0.json
```

Route files are YAML with a top-level `routes:` list. Paths in `body_file` and in `POST /__admin/scenario` are relative to the fixture root and cannot escape it.

## Run locally

```bash
python -m tools.integration_validation.mock_server.main \
  --fixture-root integrations/datadog/validation/mock \
  --port 9000
```

Then, for example:

```bash
curl -X POST http://127.0.0.1:9000/__admin/scenario \
  -H 'Content-Type: application/json' \
  -d '{"routes": ["routes/team.yaml"]}'

curl 'http://127.0.0.1:9000/api/v2/team?page=0'

curl http://127.0.0.1:9000/__admin/journal
```

## Package map

| Module | Role |
| --- | --- |
| `main.py` / `cli.py` | Entry point and uvicorn bind |
| `app.py` | FastAPI app: admin router + catch-all |
| `admin.py` | `/__admin` endpoints |
| `request_handler.py` | Parse, match, journal, respond |
| `matcher.py` | Route selection |
| `responder.py` | Body / sequence rendering |
| `loader.py` / `models.py` | Route YAML load + schema |

Design context: [Ocean Integration Validation](https://app.notion.com/p/41b9be8ff7e381be9156e671a96f9842) (§5 Mock server).
