# Fake integration verification map

This directory is the maintained source for verifying the fake integration against the local Port API. Read this index before driving, then use the matching feature file as the recipe.

## Baseline preconditions

- The ocean repo is the working directory for every command below.
- `integrations/fake-integration/.env` has uncommented local values for `OCEAN__PORT__CLIENT_ID`, `OCEAN__PORT__CLIENT_SECRET`, `OCEAN__PORT__BASE_URL`, and `OCEAN__INTEGRATION__IDENTIFIER`.
- The integration virtualenv exists. `make install` and `make install/local-core` from `integrations/fake-integration` create it when `doctor` says it is missing.
- Port is reachable at the base URL in that `.env`.
- Nothing else is listening on port 8000. `fake_org_data/fake_client.py` calls `http://localhost:8000/integration`.
- One sail at a time. The integration identifier in `.env` is shared catalog state.
- Run `doctor` and require `"ok": true` before the first drive.

## Driving conventions

- Start every recipe from the baseline unless its preconditions say otherwise.
- Treat every command as literal. Keep quoted strings and flags unchanged.
- Run the harness with `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py`.
- Do not print `.env` values. The script reads them.
- Leave files under `integrations/fake-integration/.verify/evidence/` in place during cleanup.

## Proof and skip reporting

- Capture the command and the resulting Port or HTTP state together with the process exit.
- Proof is the `summary.json` for that drive.
- A resync proof includes a new `completed` resync and a non-zero entity count for every configured kind.
- A route proof includes HTTP 200 and a non-empty `results` list.
- A kind-shape proof includes the posted raw object present on `GET /v1/integration/{identifier}/kinds` in the same command, before a later sail.
- A mapping proof includes a later sail whose catalog titles match the patched jq, then a restore sail whose titles match the backup.
- Record the feature file and the command with every artifact.
- Report an unreachable path with the command that failed and the unmet precondition.
- Do not report a skipped entry point as verified through a different command.

## Feature entry contract

Each feature file starts with an H1 and one paragraph. It then uses these four H2 sections, in order.

1. `Sub-features`
2. `How to get to it (user POV)`
3. `Driving it with verify_fake_integration.py`
4. `Gotchas`

## Features

- [Resync the catalog](./resync.md) runs one local sail and checks that each configured kind has entities.
- [Fake third-party routes](./fake-routes.md) serves the integration and reads offices, teams, projects, and one department's people.
- [Raw kind shapes](./kind-shapes.md) builds raw objects from the fake org generator and posts them as kind examples.
- [Mapping scenarios](./mapping.md) patches the mapping on the existing integration and runs a new sail.
