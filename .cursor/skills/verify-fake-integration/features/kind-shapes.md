# Raw kind shapes

Raw kind shapes are the JSON objects a kind emits before mapping. The harness builds them from the fake org data modules and can post them onto the integration that already exists.

## Sub-features

- `shapes-print` prints one or more raw objects and their field names.
- `shapes-post` stores those objects as the kind's examples and reads them back.
- `shapes-file` posts a JSON file for a kind that has no built-in producer.

## How to get to it (user POV)

- Generate a fake person or fake project payload.
- Store that payload as the raw example for its kind on the existing integration.
- For a new kind, supply a JSON example, store it, then add a mapping with the mapping feature.

## Driving it with verify_fake_integration.py

Preconditions:

- `doctor` printed `"ok": true`.
- `sync` has already created the integration, or `doctor` reports `integration_exists` true.

- **Print a person.** Build one raw person. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py shapes --kind fake-person --count 1`. The printed JSON has `"ok": true`, `source` `persons`, and `keys` that include `id`, `name`, `email`, `status`, `age`, `department`, and `bio`.
- **Post a project.** Store one raw project and read it back. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py shapes --kind fake-project --count 1 --post`. The printed JSON has `posted` true and `posted_examples_found` true.
- **Post a file.** Store a caller-supplied object. Run `integrations/fake-integration/.venv/bin/python .cursor/skills/verify-fake-integration/scripts/verify_fake_integration.py shapes --kind <kind> --file <path> --post`. `posted_examples_found` is true when each posted object is stored unchanged.
- **Proof.** Keep the `shapes` `summary.json`. It contains the ids, the field names, and `posted_examples_found`.

## Gotchas

- `fake-person` comes from `generate_fake_persons` and `fake-project` from `generate_fake_projects` in `fake_org_data/generator.py`. Departments, offices, and teams come from `fake_org_data/static.py`.
- A posted example does not create a catalog entity. Catalog entities appear only after a sail whose `integration.py` handler yields that kind.
- A new kind needs a generator or a `--file` payload, a route if resync should call HTTP, an `@ocean.on_resync("<kind>")` handler in `integration.py`, and a mapping resource applied after the integration exists.
- Posting an example replaces the visible sample set Port keeps for that kind until the next sail. A sail sends fresh examples and overwrites that set. Prove `posted_examples_found` on the shapes command itself, before another sail. The check compares the whole posted object. `fake-project` ids such as `project-001` already exist from earlier sails.
