# Mapping scenarios

Mapping scenarios change the jq on an integration that already exists, then start a new sail so that process loads the patched config.

## Sub-features

- `mapping-show` prints the stored resource for one kind.
- `mapping-patch` replaces one mapping field and runs a sail.
- `mapping-restore` writes the pre-scenario config back and runs a sail.
- `mapping-add` appends a resource for a kind that was not in the config.

## How to get to it (user POV)

- Create the integration by running it once.
- Change a kind's mapping in Port.
- Run the integration again and read the catalog titles.
- Put the previous mapping back and run it again.

## Driving it with verify_fake_integration.py

Preconditions:

- `doctor` printed `"ok": true`, `integration_exists` true, and `"listener": "free"`.
- No mapping backup is left from an unfinished scenario. If `integrations/fake-integration/.verify/state/mapping-backup.json` exists, run `mapping restore --run` before a new scenario.

- **Show the department mapping.** Read the stored resource. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py mapping show --kind fake-department`. The printed JSON has `"ok": true` and `resource.kind` `fake-department`.
- **Point title at a marked name.** Patch title, then sail. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py mapping apply --kind fake-department --map 'title=.name + "-mapped"' --run`. The printed JSON has `"ok": true`, `replaced` containing `fake-department`, `ran` true, and `resync_is_new` true.
- **Read the marked titles.** Check every department entity. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py entities --blueprint fake-department --title-suffix=-mapped`. The printed JSON has `"ok": true` and `matched` equal to `count`.
- **Restore and sail.** Put the backup config back and sail. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py mapping restore --run`. The printed JSON has `"ok": true` and `resync_is_new` true.
- **Confirm the mark is gone.** Read departments again. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py entities --blueprint fake-department --title-suffix-absent=-mapped`. The printed JSON has `"ok": true` and `matched` 0.
- **Add a resource from a file.** Append or replace a kind from JSON. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py mapping apply --file <path> --run`. Use this when the kind is absent. `--map` only edits a kind that is already stored.
- **Proof.** Keep the apply, entities, and restore `summary.json` files. Together they show the patched jq, the marked titles, and the restored titles.

## Gotchas

- `POST /v1/integration/{identifier}/config` returns 404 on the local API. The harness uses `PATCH`.
- Department `id` and `name` are the same string. Changing title from `.name` to `.id` does not change the catalog. Use a marker such as `.name + "-mapped"`.
- The first `mapping apply` stores the original config. A second apply does not overwrite that backup. `mapping restore` deletes the backup after the patch.
- `stop` does not restore a mapping. A scenario that should leave the shared integration unchanged ends on `mapping restore --run`.
- A kind with a mapping and no `@ocean.on_resync` handler yields no entities on the next sail.
- A serve process keeps the mapping it loaded at startup. Scenario sails use `sync`, which is a new process.
- A suffix that starts with `-` has to be passed as `--title-suffix=-mapped`. A space makes argparse treat it as another flag.
