# Running integration validation

How to run an integration's validation scenarios end to end. Both
`validate-integration-change` and `create-integration-validation` use this loop.

Source of truth for formats and behavior:
- `tools/integration_validation/runner/README.md` (scenarios, expected entities, report, exit codes)
- `tools/integration_validation/mock_server/README.md` (routes, matching, admin API)

## Prerequisites

- Repo root venv exists (`.venv/` at the repo root): it runs the runner and the mock.
- The integration's venv exists (`make install` in `integrations/<name>/`): the runner uses its `ocean`.
- `integrations/<name>/.env` has `OCEAN__PORT__CLIENT_ID`, `OCEAN__PORT__CLIENT_SECRET`,
  `OCEAN__PORT__BASE_URL` and `OCEAN__INTEGRATION__TYPE`. If any is missing, ask the
  developer to add it. Never read or print the values, and never ask for 3rd-party credentials.

## The loop

All `make` commands run from `integrations/<name>/`.

1. **Start the mock** in the background and keep its terminal:

   ```bash
   make validate-mock            # PORT=9001 to use another port
   ```

   Wait until it answers: `curl -s http://127.0.0.1:9000/__admin/journal`.

2. **For each scenario, one at a time** (the mock serves one scenario's routes at a time):

   a. Read the scenario's `routes` list from `validation/scenarios.yaml`.

   b. Load them. This also resets the journal, call counts and sequences:

      ```bash
      curl -s -X POST http://127.0.0.1:9000/__admin/scenario \
        -H 'Content-Type: application/json' \
        -d '{"routes": ["routes/team.yaml", "routes/user.yaml"]}'
      ```

      A 4xx answer means a route file is invalid; the message names the file.

   c. Run the scenario with an absolute report path:

      ```bash
      make validate ARGS="--scenario happy_path --report /tmp/validate-<name>-happy_path.json"
      ```

      Add `--mock-base-url http://127.0.0.1:<port>` when the mock is not on 9000.

3. **Stop the mock** when done, also after a failure.

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
