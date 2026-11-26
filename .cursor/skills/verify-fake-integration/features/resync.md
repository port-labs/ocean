# Resync the catalog

Resync starts the fake integration with the local `.env`, waits until that sail exits, and checks that Port stored a new completed resync plus at least one entity for every kind in the integration config.

## Sub-features

- `resync-once` runs one sail and requires a completed resync that started during this command.
- `resync-entities` requires a non-zero entity count for every configured kind.

## How to get to it (user POV)

- From `integrations/fake-integration`, start the integration so it performs one resync and exits.
- In Port, open the entities for `fake-department`, `fake-person`, `fake-office`, `fake-team`, and `fake-project`.

## Driving it with verify_fake_integration.py

Preconditions:

- `doctor` printed `"ok": true` and `"listener": "free"`.
- Port 8000 is not in use.

- **Run one sail.** Start the integration and let it exit. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py sync`. The printed JSON has `"ok": true`, `exit_code` 0, `resync.status` `completed`, and `resync_is_new` true.
- **Confirm entities.** Read `entity_counts` in that same JSON. Every kind has `count` of at least 1.
- **Proof.** Keep `integrations/fake-integration/.verify/evidence/<run-id>/summary.json` and `sail.log`. `summary.json` contains the resync timestamps and the per-kind counts.

## Gotchas

- The local `.env` sets `OCEAN__EVENT_LISTENER__TYPE=ONCE`. The process is supposed to exit. A still-running sail after `sync` returns is a failure. Run `stop`, then read `log_tail`.
- Person and project counts follow the integration config (`entityAmount`, `singleDepartmentRun`). Assert a count of at least 1, not a fixed total.
- An old `resyncState.status` of `completed` from a previous sail does not pass. `resync_is_new` must be true.
- Do not start `serve` and `sync` together. Both need port 8000.
- `fake-person` ids come from `faker` passport numbers. The generator default is 400 people per department when the integration amount is unset or negative. With `entityDeletionThreshold` at 0.9, a resync that would delete nearly every previous person keeps those entities. The person count grows on each sail. Offices, teams, projects, and departments keep stable ids.
- `log_notes.dsp_fallback` true means the log contains `falling back to ocean-core`. `OCEAN__PROCESSING_MODE=dsp` in `.env` is not enough when the org flags `LAKEHOUSE_ELIGIBLE` and `DATA_SOURCE_PROCESSOR_ENABLED` are off. `ok` can still be true.
- `log_notes.log_pickling_error` true means loguru failed to pickle an `ObjectKind` while writing the log. That traceback is not the resync result. Use `ok` and `resync.status`.
