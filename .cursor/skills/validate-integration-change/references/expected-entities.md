# Expected entities

How the agent treats `validation/expected/<scenario>/` depends on what the change is meant to
do. Pick the mode in step 1 of the skill, per kind, before running anything.

Snapshot format and comparison rules are in `tools/integration_validation/runner/README.md`
(*Expected entities*).

## Modes

| Mode | When | Expected snapshots |
| --- | --- | --- |
| **Intended change** | The change is meant to alter entities: a new kind, a new or changed blueprint property or relation, a mapping change in `port-app-config.yaml`, a new selector option | The agent writes the new expectation by hand **before** the run, only for the affected blueprints and fields |
| **Regression** | The change must not alter entities: client, auth, pagination, retries, refactors, dependency bumps | Frozen. The agent does not create, edit or regenerate any snapshot file |

A diff can be both: intended change for the kinds it touches, regression for every other
kind. Infer the mode from `git diff` (`.port/resources/blueprints.json`,
`.port/resources/port-app-config.yaml` and new kinds in `main.py` point to intended change;
`clients/` and exporters alone point to regression). If a client change also changes the
data a mapping reads (a new field fetched, a renamed key), treat the affected kinds as
intended change. When unclear, ask the developer which kinds are expected to change.

## Intended change: writing the expectation

The point is an independent prediction: work out what Port should contain from the mock
data and the mapping, **without** looking at what the integration produced.

1. For each affected kind, read the mapping in `port-app-config.yaml` (plus the scenario's
   `port_app_config_overrides`) and the mock bodies the scenario's routes serve.
2. Evaluate the JQ by hand for every item the mock returns: `identifier`, `title`,
   `properties.*`, `relations.*`, `team` if mapped. Apply the client's transformations too
   (enrichment, field renames, filters) by reading the client and exporter code.
3. Edit `validation/expected/<scenario>/<blueprint>.json` (real blueprint identifier, not
   the suffixed one):
   - A new kind: create the file with every entity the scenario should produce.
   - A new or changed property: change only that field on each entity; leave every other
     field as it is.
   - A removed property: remove that key from each entity.
   - Match the shape of the existing snapshots: keys sorted, `relations: {}` when there are
     none, and an explicit `null` where the JQ yields `null` (a missing key is not `null`).
4. If the mock bodies lack the vendor fields the new mapping reads, add them to the bodies
   and the response model first (bootstrapping reference, steps 2 and 3).
5. Don't touch snapshots of kinds that are in regression mode.

Writing the files before the run also stops the runner from seeding snapshots from the
run itself.

### When the run differs from the prediction

For each `entity_diff` entry, decide which side is wrong by re-reading the mapping and the
mock data:
- **Your prediction is wrong** (a JQ misread, a missed transformation): fix the snapshot and
  tell the developer what you misread.
- **The integration is wrong**: report it as a bug with the field, the expected and actual
  values, and the mapping line. Don't change the snapshot to match.

Never copy the actual values into the snapshot just to make the scenario pass, and don't use
`--update-expected` in this mode.

## Regression: frozen snapshots

1. Before the run, check that `validation/expected/<scenario>/` has at least one `*.json`
   file for every scenario you'll run. If it doesn't, the runner would seed snapshots from
   this run and report `matched`, which proves nothing. Stop, and tell the developer that
   regression can't be checked for that scenario until a reviewed baseline exists (seeded
   from the base branch, or written by hand as in intended change).
2. Run the scenarios. `comparison.status: matched` means no regression for those kinds.
3. Any `different` is a regression until proven otherwise. Explain each `entity_diff` entry
   and point at the code change that likely caused it. Don't edit the snapshots and don't
   run `--update-expected`. If the developer says the change was intended after all, switch
   those kinds to intended change and write the expectation by hand.
