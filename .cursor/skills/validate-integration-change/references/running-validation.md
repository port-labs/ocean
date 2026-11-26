# Running integration validation

How to run an integration's validation scenarios end to end. This loop needs an existing
`validation/`; if there isn't one, follow [bootstrapping-validation.md](bootstrapping-validation.md)
first.

Source of truth for formats and behavior:
- `tools/integration_validation/runner/README.md` (scenarios, expected entities, report, exit codes)
- `tools/integration_validation/mock_server/README.md` (routes, matching, admin API)

## Prerequisites

Complete **mandatory environment** checks first. Do not start the mock or run `make validate`
until they pass (or the developer explicitly asks to continue despite a warning).

### Mandatory environment

The runner exits **2** (`status: error` in the report) when setup is incomplete. These must be
set in the process environment or in `integrations/<name>/.env` (loaded during runner preflight):

| Variable | Required for |
| --- | --- |
| `OCEAN__PORT__CLIENT_ID` | Port API authentication |
| `OCEAN__PORT__CLIENT_SECRET` | Port API authentication |
| `OCEAN__PORT__BASE_URL` | Port org API base URL |
| `OCEAN__INTEGRATION__TYPE` | Integration type in Port (usually the folder name, e.g. `pagerduty`) |

Validation mock scenarios inject vendor settings via `defaults.integration_config` in
`scenarios.yaml` (for example a fake API token). Missing entries in `.env` for **3rd-party
vendor** credentials are expected during validation; only the four variables above are
mandatory.

**Agent preflight (before the mock):**

1. Confirm `integrations/<name>/.env` exists or the developer said the vars are exported in
   the shell.
2. Detect which of the four keys are absent or have an empty value. Check `.env` and the
   current environment; inspect only key names and presence — **never** read, log, echo, or
   repeat secret values in chat.
3. If anything is missing, **stop** and tell the developer exactly which **key names** to add
   and where (`integrations/<name>/.env`). Do not start `validate-mock`, probe port 9000, or
   run `make validate` until they confirm the file is ready (unless they explicitly override).
4. When reporting success, you may say all mandatory keys are present; do not list values.

Safe check from `integrations/<name>/` using the repo root venv (prints only missing key
names or `ok`):

```bash
cd ../.. && .venv/bin/python - <<'PY'
from pathlib import Path
import os

integration = Path("integrations/<name>")  # substitute <name>
required = (
    "OCEAN__PORT__CLIENT_ID",
    "OCEAN__PORT__CLIENT_SECRET",
    "OCEAN__PORT__BASE_URL",
    "OCEAN__INTEGRATION__TYPE",
)

def from_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip("'\"")
    return out

file_vars = from_env_file(integration / ".env")
missing = [
    key
    for key in required
    if not (os.environ.get(key) or file_vars.get(key))
]
if missing:
    print("missing:", ", ".join(missing))
    raise SystemExit(1)
print("ok")
PY
```

### Tooling

- Repo root venv exists (`.venv/` at the repo root): it runs the runner and the mock.
- The integration's venv exists (`make install` in `integrations/<name>/`): the runner uses
  its `ocean`.

Never ask for 3rd-party vendor credentials for validation runs.

## Mock port selection

Default mock port is **9000**. Something else may already bind it (a stale mock, another
app). The agent must pick a working port before loading scenarios and running `make validate`.

1. From `integrations/<name>/`, try ports in order **9000, 9001, 9002, …** up to **9010**
   (or until one succeeds):

   ```bash
   PORT=9000 make validate-mock   # background; default PORT is 9000 when omitted
   ```

2. After a short wait, probe the admin API:

   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:<port>/__admin/journal
   ```

   - **2xx** → use this `<port>` as `MOCK_PORT` for the rest of the session.
   - **Non-2xx or connection refused** → stop the background job if it exited; try the next
     port. If the Makefile process failed immediately with **address already in use** /
     `errno 48`, do not assume something on that port is *this* mock — try the next port.
   - If another mock is already healthy on 9000 (journal returns JSON), you may reuse it;
     still pass `--mock-base-url http://127.0.0.1:9000` on `make validate` so the runner
     matches the integration subprocess.

3. Set `MOCK_BASE_URL=http://127.0.0.1:<MOCK_PORT>` and use it for every admin `curl` and
   for `make validate ARGS="... --mock-base-url $MOCK_BASE_URL"`.

4. When stopping the mock at the end, kill only the process you started on `MOCK_PORT`
   (for example `lsof -ti :$MOCK_PORT`), not every listener on 9000, unless you started on
   9000 and are sure it is yours.

Tell the developer which port was used if it was not 9000.

## The loop

All `make` commands run from `integrations/<name>/`. Complete **Mock port selection** first.

1. **Start the mock** in the background on `MOCK_PORT` (see above).

2. **For each scenario, one at a time** (the mock serves one scenario's routes at a time):

   a. Read the scenario's `routes` list from `validation/scenarios.yaml`.

   b. Load them. This also resets the journal, call counts and sequences:

      ```bash
      curl -s -X POST "$MOCK_BASE_URL/__admin/scenario" \
        -H 'Content-Type: application/json' \
        -d '{"routes": ["routes/team.yaml", "routes/user.yaml"]}'
      ```

      A 4xx answer means a route file is invalid; the message names the file.

   c. Run the scenario with an absolute report path and the same mock base URL:

      ```bash
      make validate ARGS="--scenario happy_path --mock-base-url $MOCK_BASE_URL --report /tmp/validate-<name>-happy_path.json"
      ```

3. **Stop the mock** you started when done, also after a failure.

Exit codes: `0` passed, `1` validation failed, `2` setup error (the report's `error` says why).

## Reading the report

The report is written on every exit, including setup errors.

| Field | Meaning |
| --- | --- |
| `status` | `passed`, `failed`, or `error` (setup or Port error; see `error`) |
| `scenarios[].passed` | `true` only when `ocean sail` completed, entity comparison is `matched`, and there are no unmatched mock requests (unless `expect.unmatched_requests: allow`). Does not consult `collection.resync_status` directly. |
| `scenarios[].integration` | `returncode`, `timed_out`, `stdout_tail`, `stderr_tail` of `ocean sail` |
| `scenarios[].collection.resync_status` | What Port reports for the resync: `completed`, `failed`, `aborted`, `running`, or `missing`. When not `completed`, the runner does not write or refresh snapshots in `validation/expected/`. |
| `scenarios[].collection.mock.unmatched_requests` | Requests no route matched; they fail the scenario unless it sets `expect.unmatched_requests: allow` |
| `scenarios[].collection.mock.unused_routes` | Loaded routes the integration never called |
| `scenarios[].comparison.status` | `matched` or `different` only (`tools/integration_validation/runner/core/statuses.py`) |
| `scenarios[].comparison.expected_dir` | Directory of snapshot JSON files compared for this scenario |
| `scenarios[].comparison.entity_diff` | Populated when status is `different`: per blueprint, `added`, `removed`, `changed` (field path, expected, actual) |
| `scenarios[].unverified_routes` | Routes marked `verified: false` |
| `scenarios[].port.cleanup_leftovers` | Port resources the run could not delete |

When `validation/expected/<scenario>/` is missing and the resync completes, the runner writes snapshots from the collected entities, then compares—so the first successful run usually shows `comparison.status: matched`, not a separate “new” status. Review those files before committing. With `--update-expected`, snapshots are overwritten the same way before the diff.

## Known limits

- Response bodies are returned as written: there is no `{{base_url}}` templating, only
  `{param}` path parameters in `body_file` names. An integration that follows absolute
  "next page" URLs from the response cannot be paginated against the mock yet. Say so
  instead of working around it.
- `--update-expected` overwrites `validation/expected/<scenario>/`. Only run it after the
  developer approved the diff.
