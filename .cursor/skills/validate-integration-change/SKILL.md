---
name: validate-integration-change
description: >-
  Validate any change under integrations/ against a local HTTP vendor stub and
  a sandbox Port org, using response shapes from the vendor docs and no real
  vendor credentials. Use whenever implementing, fixing, or refactoring an
  Ocean integration: adding or changing a kind, fixing a bug, or changing
  client, mapping, config, webhook, or other internal logic. Also use when
  asked to validate an integration change, run agentic integration validation,
  or prove a mapping or client change with a stub. Finish when the sail script
  exits 0. If it exits with a missing Port credentials error, do not retry.
  Never run ocean sail directly. If the script is stuck, stop.
---

# Validate an integration change

Run this for integration work, not only when the user says "validate". That includes adding or changing a kind, fixing a bug, and changing client, mapping, config, webhook, or other internal logic. Prove the change by stubbing the third-party API locally, sailing once into a sandbox Port org, and asserting entities. The task is done when the sail script exits 0.

## Steps

1. **Read the docs** for the vendor endpoints the change touches. Prefer official REST/GraphQL docs over guessing response shapes.
2. **Write the change** in the integration (client, mapping, config, etc.).
3. **Write an expectations file** (YAML). It must name `blueprint`. Add at least one of: `count`, `identifier`, a mapped `property` (`name`/`value`), or `absent`. Optionally include `blueprint_definition` (created only if missing), `host_env` (env var set to the stub URL), and `env` (extra env; `${STUB_URL}` is expanded).
4. **Start the stub** (if not already running):

   ```bash
   python -m tools.vendor_stub --port 8765
   ```

5. **Register routes** for every third-party call the resync will make (including startup webhook registration — see below). Use the admin CLI or HTTP:

   ```bash
   python -m tools.vendor_stub.cli register --file /tmp/reg.json
   python -m tools.vendor_stub.cli paginate --file /tmp/pages.json
   python -m tools.vendor_stub.cli reset
   python -m tools.vendor_stub.cli unmatched
   ```

   Registration fields: `method`, `path` or `path_regex`, optional `query`, `headers`, `body_contains`, `body_field`, `priority`, `times` (int or response sequence), and `response` (`status`, `body`, `headers`).
6. **Response files** — while preparing bodies, write them under `integrations/<name>/mock_responses/`. Include the doc URL and the date in the file (comment or `_meta`). A later run may reuse a file only when every mapped field needed for this change is already present in it; otherwise rewrite from the docs.
7. **Run the sail script**:

   ```bash
   python scripts/validate_integration_sail.py \
     --integration integrations/<name> \
     --expectations /path/to/expectations.yaml \
     --stub-url http://127.0.0.1:8765 \
     --host-env OCEAN__INTEGRATION__CONFIG__<HOST_FIELD>
   ```

   The script loads Port credentials itself. Do not read `.env`. Never pass credentials as CLI args.
   Do not run `ocean`, `ocean sail`, or `python -m port_ocean` yourself. This script is the only way to start the integration.
   Cleanup runs by default. It deletes this run's integration, its entities, and a blueprint this run created. Do not pass `--no-cleanup` unless the user explicitly asks to keep those Port resources.
8. **Stop when it exits 0.** If the output contains `missing Port credentials`, stop. Do not reset, re-register, or re-run. Tell the user the code changes, expectations, and mocks are in place, and validation did not run because Port credentials are not configured. On any other failure, fix the registration, the expectations, or the integration change and run the script once more. If that fails again, or you are stuck on startup or imports, stop and report the script output. Do not launch Ocean another way.

## Startup webhooks (C3)

If the integration registers a webhook with the vendor on startup, stub that route too. Otherwise sail fails before the resync and the run is useless.

## Minimal expectations example

```yaml
blueprint: githubRepository
count: 1
identifier: example-repo
property:
  name: default_branch
  value: main
host_env: OCEAN__INTEGRATION__CONFIG__GITHUB_HOST
env:
  OCEAN__INTEGRATION__CONFIG__GITHUB_TOKEN: "dummy"
```
