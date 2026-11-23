# Integration validation runner

Loads `<integration>/validation/scenarios.yaml`, runs preflight (layout, Port credentials, `port_app_config`, per-scenario `blueprints`), prepares an isolated copy of the integration in Port for each scenario, and will orchestrate mock + `ocean sail` + entity diff in follow-up work.

`defaults.blueprints` defaults to `.port/resources/blueprints.json`. A scenario may override with its own path (for example `validation/fixtures/blueprints.json` when the default file is missing kinds under test).

## Port preparation

For each scenario, before writing anything to Port, the runner builds a plan:

1. Loads the scenario's blueprints file and suffixes every identifier with the scenario name (`datadogTeam` → `datadogTeam-happy-path`). Relation and aggregation targets inside the set are rewritten; targets outside it (for example `_user`) are kept.
2. Builds the mapping: `defaults.port_app_config`, filtered to the scenario's `kinds`, then each `port_app_config_overrides` entry deep-merged into the resources of the same `kind`.
3. Points every mapping's `blueprint` at the suffixed identifiers. Only JQ string literals (`'"datadogTeam"'`) are supported; a dynamic expression or a blueprint missing from the file fails with exit code `2`, since it would write outside the run's blueprints.

Then it creates the blueprints and creates the integration `validate-<integration>-<scenario>` (truncated to Port's 53-character limit) with that mapping. The integration uses the `Default` resources origin and `arePortResourcesInitialized: true`, so `ocean sail` keeps the mapping and creates no default resources. If any step fails, the scenario's integration and blueprints are deleted.

Blueprints are applied sequentially in array order. A relation target must appear earlier in the blueprints file (parents first, children last), because Port rejects a relation to a blueprint that does not exist yet. Targets outside the set (for example `_user`) are not affected.

At the end of each scenario, the integration and the run's blueprints (with their entities) are deleted, unless `--skip-cleanup` is passed. Names are fixed per scenario, so each scenario first deletes whatever an earlier run left behind (for example after `--skip-cleanup`).

## Run locally

From the repo root, against an integration directory:

```bash
python -m tools.integration_validation.runner integrations/datadog \
  --scenario happy_path \
  --report /tmp/validate-report.json
```

Options: `--scenario NAME` (repeatable), `--update-expected`, `--skip-cleanup`, `--report PATH`.

Exit codes: `0` pass, `1` validation failed (for example Port rejected a blueprint or the mapping), `2` setup/preflight error.
