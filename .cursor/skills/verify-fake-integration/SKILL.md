---
name: verify-fake-integration
description: >-
  Launch Ocean's fake integration against the local Port API, prove a resync
  wrote catalog entities, post raw kind shapes, and patch mappings on an
  integration that already exists. Use when checking the fake integration
  locally, posting a kind example from the fake org generator, or running a
  sail again after a mapping change.
---

# Verify the fake integration

Drive `integrations/fake-integration` against the local Port API named in its `.env`. The harness is [scripts/verify_fake_integration.py](scripts/verify_fake_integration.py). Run that file with the integration virtualenv. Read [features/README.md](features/README.md) before a drive, then follow one feature file to the end.

The active, uncommented `.env` lines are the launch environment. The script overlays them onto the sail process.

## Launch

From the ocean repo root:

```bash
integrations/fake-integration/.venv/bin/python \
  .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py sync
```

`sync` runs `ocean sail` in `integrations/fake-integration`. The checked-in local env uses the ONCE listener, so the process exits after one resync. Done when the printed JSON has `"ok": true`, `resync.status` is `completed`, and `resync_is_new` is true.

`serve` keeps the fake HTTP routes up. It sets the listener to polling and turns resync-on-start off. Done when the printed JSON has `"ok": true` and `health.body.status` is `healthy`.

If `.venv` is missing, from `integrations/fake-integration` run `make install` and `make install/local-core`. Done when `doctor` reports `port_ocean.ok` true and `port_ocean.file` is inside this checkout.

## Doctor

```bash
integrations/fake-integration/.venv/bin/python \
  .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py doctor
```

Run this before the first drive, and again after a sail exits unexpectedly. Done when `"ok": true`. That means the token works, `port_ocean` is this checkout, and port 8000 is free or owned by a pid this skill recorded. `"listener": "foreign"` means stop. Do not drive that process.

## Drive

Follow the feature file. Keep every flag and quoted string. `shapes --post` stores raw examples. `mapping apply` changes the config of the integration that already exists. `mapping apply --run` and `mapping restore --run` start a new sail, so that process loads the patched config.

Port returns 404 for `POST /v1/integration/{identifier}/config`. The mapping write is `PATCH /v1/integration/{identifier}/config` with a body of `{"config": ...}`. Raw kind examples are `POST /v1/integration/{identifier}/kinds/{kind}/examples` with a body of `{"examples": [...]}`. The script issues those calls. Do not invent a second client.

## Evidence

Each drive writes `integrations/fake-integration/.verify/evidence/<run-id>/summary.json`. A sail also leaves `sail.log` in that directory. The summary records the command, the exit code, and the Port or HTTP state that proves the result. Cleanup leaves this directory in place.

## Cleanup

```bash
integrations/fake-integration/.venv/bin/python \
  .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py stop
```

`stop` signals the pid recorded by `serve` or `sync`. It does not delete the Port integration, catalog entities, mapping backup, or evidence. After a mapping scenario, run `mapping restore --run` when the feature file says to put the shared integration back. Confirm `summary.json` is still on disk after `stop`.

## Helpers

Invoke the virtualenv Python on `scripts/verify_fake_integration.py`. Subcommands:

- `doctor`
- `sync [--timeout 180]`
- `serve [--timeout 90]`
- `stop`
- `routes`
- `shapes --kind <kind> [--count N] [--file path] [--post]`
- `entities --blueprint <blueprint> [--limit N] [--title-suffix=text] [--title-suffix-absent=text]`
- `mapping show --kind <kind>`
- `mapping apply (--file path | --kind <kind> --map key=jq) [--run]`
- `mapping restore [--run]`

`shapes` without `--file` builds the raw objects from `fake_org_data/generator.py` for `fake-person` and `fake-project`, and from `fake_org_data/static.py` for `fake-department`, `fake-office`, and `fake-team`. `--file` is a JSON list, or an object with an `examples` list, and it can name a kind that has no generator yet.

`mapping apply --file` is one resource object, a list of resources, or an object with `resources`. Apply replaces the stored resource with the same `kind`, or appends a new kind. `--map` edits the top-level keys of an existing kind's mapping (`title`, `identifier`, `blueprint`, `icon`, `team`). The first apply saves the previous config. A later apply keeps that original backup. `mapping restore` patches the backup back and deletes the backup file.

A kind produces catalog entities only when `integration.py` registers `@ocean.on_resync` for it. Posting an example and a mapping does not add that handler.
