# Integration validation runner

Loads `<integration>/validation/scenarios.yaml`, runs preflight (layout, Port credentials, `port_app_config`, per-scenario `blueprints`), prepares an isolated copy of the integration in Port for each scenario, and optionally runs `ocean sail -O` against a mock that you start separately.

`defaults.blueprints` defaults to `.port/resources/blueprints.json`. A scenario may override with its own path (for example `validation/fixtures/blueprints.json` when the default file is missing kinds under test).

## Port preparation

For each scenario, before writing anything to Port, the runner builds a plan:

1. Loads the scenario's blueprints file and suffixes every identifier with the scenario name (`datadogTeam` → `datadogTeam-happy-path`). Relation and aggregation targets inside the set are rewritten; targets outside it (for example `_user`) are kept.
2. Builds the mapping: `defaults.port_app_config`, filtered to the scenario's `kinds`, then each `port_app_config_overrides` entry deep-merged into the resources of the same `kind`.
3. Points every mapping's `blueprint` at the suffixed identifiers. Only JQ string literals (`'"datadogTeam"'`) are supported; a dynamic expression or a blueprint missing from the file fails with exit code `2`, since it would write outside the run's blueprints.

Then it creates the blueprints and creates the integration `validate-<integration>-<scenario>` (truncated to Port's 53-character limit) with that mapping. The integration uses the `Default` resources origin and `arePortResourcesInitialized: true`, so `ocean sail` keeps the mapping and creates no default resources. If any step fails, the scenario's integration and blueprints are deleted.

Blueprints are applied sequentially in array order. A relation target must appear earlier in the blueprints file (parents first, children last), because Port rejects a relation to a blueprint that does not exist yet. Targets outside the set (for example `_user`) are not affected.

Each scenario is wrapped in `try/finally`: after Port preparation (and optional `ocean sail`), the run deletes its integration and suffixed blueprints with entities—on success or failure—unless `--skip-cleanup` is set. Only resources created for that run are touched. Names are fixed per scenario, so preparation first removes leftovers from an earlier `--skip-cleanup` run.

## Run locally

From the repo root, against an integration directory:

```bash
# Terminal 1: mock server + scenario load (admin API — see tools/integration_validation/mock_server)

# Terminal 2: Port prep + one-shot sail (mock must already be listening)
python -m tools.integration_validation.runner integrations/datadog \
  --scenario happy_path \
  --report /tmp/validate-report.json
```

Or from the integration directory: `make validate-mock` (mock on `PORT`, default 9000) and `make validate ARGS="--scenario happy_path"`. Both use the repo root venv.

Options: `--scenario NAME` (repeatable), `--update-expected`, `--skip-cleanup`, `--report PATH`, `--mock-base-url URL` (default `http://127.0.0.1:9000`; the runner does not start the mock), `--integration-timeout SECONDS` (subprocess limit, default 180).

The runner only reads the mock's admin API; it never loads or resets it. Load the scenario before each run and reset the mock between runs (`POST /__admin/reset`), otherwise the journal and call counts include earlier requests. Run one `--scenario` at a time, since every scenario hits whatever is loaded.

Each scenario runs `ocean sail -O` as a subprocess (`OCEAN_CLI`, else `<integration>/.venv/bin/ocean`, else `ocean` on `PATH`) with `OCEAN__EVENT_LISTENER__TYPE=ONCE`, `OCEAN__INITIALIZE_PORT_RESOURCES=false`, the run's integration identifier, and `defaults.integration_config` (plus optional per-scenario `integration_config`) rendered with `{{mock_base_url}}`. `OCEAN__BASE_URL` is stripped so the subprocess stays address-less. Pass/fail for the integration step is the subprocess exit code (entity expectations are a follow-up step).

## Collected results

After the subprocess exits and before cleanup, each scenario collects:

- the resync status Port reports for the integration (`completed`, `failed`, `aborted`, `running` or `missing`). Ocean reports the final status before `ocean sail -O` exits, so `running` here means it could not report it (for example after a timeout);
- every entity in each of the run's blueprints, searched by blueprint rather than datasource, so placeholders from `createMissingRelatedEntities` and unexpected entities are included;
- the mock's journal: all requests, unmatched requests, unused routes and per-route call counts.

A request no mock route matched fails the scenario, unless the scenario sets `expect.unmatched_requests: allow`.

## Output

The console prints one line per scenario (pass/fail, entity count, unmatched requests, expected-entities status). Only what needs attention is listed under it: an integration or resync failure, unmatched requests, entity differences, and Port resources the run left behind. A footer lists the unverified routes (`verified: false`) of the scenarios that ran, and the totals.

`--report PATH` writes the same results as JSON: overall `status` (`passed`, `failed`, or `error`) and `totals`, and for each scenario `passed`, `unverified_routes`, the `integration` subprocess result with its log tails, the `collection` (resync status, entity counts per blueprint, mock journal summary) and the `comparison`. When a setup or Port error stops the run, the report is still written, with `status: error`, the message in `error` and no scenarios.

## Expected entities

The collected entities are compared with snapshots in `validation/expected/<scenario>/`, or the folder `expect.entities` names (relative to `validation/`). There is one `<blueprint>.json` per blueprint, named with the real blueprint identifier; a blueprint without a file is expected to have no entities.

Both sides are normalized before comparing:

- `blueprint`, `createdAt`, `updatedAt`, `createdBy` and `updatedBy` are dropped, as is every path in `defaults.ignore_fields` (dotted, for example `properties.lastSeen`);
- `null` properties and relations are dropped, so `null` and a missing value compare equal;
- relation arrays and `team` are sorted, entities are sorted by identifier, and files are written with sorted keys.

Each scenario gets a comparison status, shown in the console and in the report's `comparison` section:

| Status | Meaning |
| --- | --- |
| `matched` | Entities equal the snapshots |
| `different` | Entities were added, removed or changed; the report lists each one with the changed field path, for example `properties.handle` |
| `new` | No snapshots existed, so they were written from this run |
| `updated` | `--update-expected` overwrote the snapshots with this run's result |
| `skipped` | Snapshots were due to be written, but the integration or resync did not complete, so nothing was written |

Snapshots are never written from a failed resync. Review the files `new` and `updated` write before committing them.

Exit codes: `0` pass, `1` validation failed (the integration failed, Port rejected a blueprint or the mapping, unmatched requests, entities differ from the snapshots, or snapshots were skipped), `2` setup/preflight error.
