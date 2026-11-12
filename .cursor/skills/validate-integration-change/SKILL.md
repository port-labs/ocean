---
name: validate-integration-change
# REVERT: restore the broader description below (use whenever implementing...), then
# delete disable-model-invocation so the skill can auto-suggest again.
description: >-
  Validate any change under integrations/ against a local HTTP vendor stub and
  a sandbox Port org, using response shapes from the vendor docs and no real
  vendor credentials. Use when asked to validate an integration change, run
  agentic integration validation, or prove a mapping or client change with a
  stub. Finish when the sail script exits 0. If it exits with a missing Port
  credentials error, do not retry. Never run ocean sail directly. If the
  script is stuck, stop.
# REVERT: delete the next line
disable-model-invocation: true
---

# Validate an integration change

<!-- REVERT: delete this whole "When to run" section (request-only gate) -->
## When to run

Run this only when requested (for example: "validate this integration change",
"run agentic integration validation", or an explicit ask to prove a mapping or
client change with the stub). Do not start this workflow on every integration
edit until it is confirmed to work as expected.

<!-- REVERT: restore this into description (after "vendor credentials."):
Use whenever implementing, fixing, or refactoring an Ocean integration: adding
or changing a kind, fixing a bug, or changing client, mapping, config, webhook,
or other internal logic. Also use when asked to validate an integration change,
run agentic integration validation, or prove a mapping or client change with a
stub.
-->

<!-- REVERT: uncomment the next paragraph and delete the "When requested, prove..." line below -->
<!--
Run this for integration work, not only when the user says "validate". That includes adding or changing a kind, fixing a bug, and changing client, mapping, config, webhook, or other internal logic. Prove the change by stubbing the third-party API locally, sailing once into a sandbox Port org, and asserting entities. The task is done when the sail script exits 0.
-->

<!-- REVERT: delete this line after restoring the auto-run paragraph above -->
When requested, prove the change by stubbing the third-party API locally, sailing once into a sandbox Port org, and asserting entities. The task is done when the sail script exits 0.

## Steps

1. **Read the docs** for the vendor endpoints the change touches. Prefer official REST/GraphQL docs over guessing response shapes.
2. **Write the change** in the integration (client, mapping, config, etc.).
3. **Write an expectations file** (YAML). It must name `blueprint` and include `mapping`. `mapping` is the port-app-config for this run: put only the resources the resync should ingest (the kind under test, plus any other kind that change needs). The script creates the integration with that mapping in one request, and sail keeps it. Kinds left out of `mapping.resources` are not fetched or upserted. Do not delete those kinds from the integration's `port-app-config.yml`. Add at least one of: `count`, `identifier`, a mapped `property` (`name`/`value`), or `absent`. Optionally include `blueprint_definition` (created only if missing), `host_env` (env var set to the stub URL), and `env` (extra env; `${STUB_URL}` is expanded). A relation on a kept resource still needs its target blueprint to exist.
4. **Start the stub** (if not already running):

   ```bash
   python -m tools.vendor_stub --port 8765
   ```

5. **Register routes** for every third-party call this run's resync will make, including startup webhook registration (see below). That is the resources in `mapping`, not every kind in the integration's port-app-config. Use the admin CLI or HTTP:

   ```bash
   python -m tools.vendor_stub.cli register \
     --file /tmp/reg.json \
     --model integrations/<name>/<package>/external_api_models/<resource>.py:<Class> \
     --values '{"name":"example-repo","visibility":"public"}' \
     --as-list
   python -m tools.vendor_stub.cli paginate --file /tmp/pages.json
   python -m tools.vendor_stub.cli reset
   python -m tools.vendor_stub.cli unmatched
   ```

   `--file` / `--json` supply `method`, `path` or `path_regex`, optional `query`, `headers`, `body_contains`, `body_field`, `priority`, `times` (int or response sequence), and `response` (`status`, `headers`). Do not put the response body in that file.
6. **Models** — write or extend `integrations/<name>/<package>/external_api_models/<resource>.py` as the full vendor object from the docs, not the subset this change maps. Put the doc URL and the date in the module docstring. A later run may reuse the module when it already matches that documented object. Do not add an example constructor. Do not add `from __future__ import annotations` or `model_rebuild()` unless the file has a real forward or recursive type reference that fails without them. Prefer defining nested classes before they are referenced.

   Register with `--model path/to/model.py:Class` and `--values` set to the partial body the stub should return (asserted values, identifiers, mapped fields, and fields that link to another stubbed resource). The CLI checks that partial against the full model, then registers `--values` as the HTTP body. Use `--as-list` when the endpoint returns an array. `--model` on `paginate` sets every page body from that same partial. Do not hand-write the response body in the registration file.
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
mapping:
  resources:
    - kind: repository
      selector:
        query: "true"
      port:
        entity:
          mappings:
            identifier: .name
            title: .name
            blueprint: '"githubRepository"'
            properties:
              defaultBranch: .default_branch
host_env: OCEAN__INTEGRATION__CONFIG__GITHUB_HOST
env:
  OCEAN__INTEGRATION__CONFIG__GITHUB_TOKEN: "dummy"
```
