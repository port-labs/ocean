# Integration validation runner

Loads `<integration>/validation/scenarios.yaml`, runs preflight (layout, Port credentials, `port_app_config`, per-scenario `blueprints`), and will orchestrate mock + `ocean sail` + entity diff in follow-up work.

`defaults.blueprints` defaults to `.port/resources/blueprints.json`. A scenario may override with its own path (for example `validation/fixtures/blueprints.json` when the default file is missing kinds under test).

## Run locally

From the repo root, against an integration directory:

```bash
python -m tools.integration_validation.runner integrations/datadog \
  --scenario happy_path \
  --report /tmp/validate-report.json
```

Options: `--scenario NAME` (repeatable), `--update-expected`, `--skip-cleanup`, `--report PATH`.

Exit codes: `0` pass, `1` validation failed, `2` setup/preflight error.
