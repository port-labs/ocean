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

Options: `--scenario NAME` (repeatable), `--update-expected`, `--skip-cleanup`, `--report PATH`, `--mock-base-url URL` (default `http://127.0.0.1:9000`; the runner does not start the mock), `--integration-timeout SECONDS` (subprocess limit, default 180).

Each scenario runs `ocean sail -O` as a subprocess with `OCEAN__EVENT_LISTENER__TYPE=ONCE`, `OCEAN__INITIALIZE_PORT_RESOURCES=false`, the run's integration identifier, and `defaults.integration_config` (plus optional per-scenario `integration_config`) rendered with `{{mock_base_url}}`. `OCEAN__BASE_URL` is stripped so the subprocess stays address-less. Pass/fail for the integration step is the subprocess exit code (entity expectations are a follow-up step).

Exit codes: `0` pass, `1` validation failed (for example Port rejected a blueprint or the mapping), `2` setup/preflight error.
