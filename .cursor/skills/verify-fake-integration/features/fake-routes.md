# Fake third-party routes

The running integration exposes the fake org API that its own resync client calls. Offices, teams, projects, and a department's people are HTTP responses on port 8000.

## Sub-features

- `routes-serve` keeps the process up with polling and resync-on-start off.
- `routes-read` reads offices, teams, projects, and one page of people in department `hr`.

## How to get to it (user POV)

- Start the fake integration and leave it running.
- Open `http://127.0.0.1:8000/integration/offices`.
- Open `http://127.0.0.1:8000/integration/teams`.
- Open `http://127.0.0.1:8000/integration/projects`.
- Open `http://127.0.0.1:8000/integration/department/hr/employees?limit=1&entity_kb_size=1&latency=0`.

## Driving it with verify_fake_integration.py

Preconditions:

- `doctor` printed `"ok": true` and `"listener": "free"`.
- No `sync` is in progress.

- **Serve routes.** Leave the integration running. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py serve`. The printed JSON has `"ok": true` and `health.body.status` `healthy`.
- **Read the fake API.** Request the four routes. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py routes`. Each check has `"ok": true`, `status_code` 200, and `count` of at least 1.
- **Proof.** Keep the `routes` `summary.json`. It lists each route, status code, count, and one sample id.
- **Stop the server.** Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py stop`. The `routes` summary file is still on disk.

## Gotchas

- Departments have no list route. Resync builds them from `fake_org_data/static.py`. `routes` records that kind as skipped.
- A pending Port resync request can start a resync on the first poll even when resync-on-start is off. Route checks are still valid once each response is 200.
- `stop` during that resync sets Port `resyncState.status` to `aborted`. The catalog from the previous completed sail remains. Run `sync` when you need `completed` again.
- `fake_client.py` hardcodes port 8000. Serving on another port makes resync call the wrong process.
