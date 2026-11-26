# Running integration validation

How to run an integration's validation scenarios end to end. Both
`validate-integration-change` and `create-integration-validation` use this loop.

`validate-integration-change` runs this loop only after `validation/` exists. If it does not,
the agent bootstraps via `create-integration-validation` first (same session), then continues here.

Source of truth for formats and behavior:
- `tools/integration_validation/runner/README.md` (scenarios, expected entities, report, exit codes)
- `tools/integration_validation/mock_server/README.md` (routes, matching, admin API)

## Prerequisites

- Repo root venv exists (`.venv/` at the repo root): it runs the runner and the mock.
- The integration's venv exists (`make install` in `integrations/<name>/`): the runner uses its `ocean`.
- `integrations/<name>/.env` has `OCEAN__PORT__CLIENT_ID`, `OCEAN__PORT__CLIENT_SECRET`,
  `OCEAN__PORT__BASE_URL` and `OCEAN__INTEGRATION__TYPE`. If any is missing, ask the
  developer to add it. Never read or print the values, and never ask for 3rd-party credentials.

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
| `scenarios[].passed` | The scenario's verdict |
| `scenarios[].integration` | `returncode`, `timed_out`, `stdout_tail`, `stderr_tail` of `ocean sail` |
| `scenarios[].collection.resync_status` | What Port reports for the resync |
| `scenarios[].collection.mock.unmatched_requests` | Requests no route matched; they fail the scenario unless it sets `expect.unmatched_requests: allow` |
| `scenarios[].collection.mock.unused_routes` | Loaded routes the integration never called |
| `scenarios[].comparison.status` | `matched`, `different`, `new`, `updated`, or `skipped` |
| `scenarios[].comparison.entity_diff` | Per blueprint: `added`, `removed`, `changed` (with field path, expected, actual) |
| `scenarios[].unverified_routes` | Routes marked `verified: false` |
| `scenarios[].port.cleanup_leftovers` | Port resources the run could not delete |

## Known limits

- Response bodies are returned as written: there is no `{{base_url}}` templating, only
  `{param}` path parameters in `body_file` names. An integration that follows absolute
  "next page" URLs from the response cannot be paginated against the mock yet. Say so
  instead of working around it.
- `--update-expected` overwrites `validation/expected/<scenario>/`. Only run it after the
  developer approved the diff.
