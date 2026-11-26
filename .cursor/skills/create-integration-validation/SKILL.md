---
name: create-integration-validation
description: Create mock-backed validation scenarios for an Ocean integration (validation/ folder with response models, mock routes, scenarios.yaml and expected entities). Use when the developer asks to add validation, mock scenarios or validation fixtures, when an integration has no validation/ folder yet, or when validate-integration-change needs to bootstrap before running. Requires the integration name (folder under integrations/).
---

# Create Integration Validation

Build `integrations/<name>/validation/` so the integration can be validated against a
mock vendor API and a real Port org, without vendor credentials.

Formats are defined in `tools/integration_validation/runner/README.md` and
`tools/integration_validation/mock_server/README.md`. Made-up examples of every file are in
[references/examples.md](references/examples.md). Running the scenarios is described in
[../validate-integration-change/references/running-validation.md](../validate-integration-change/references/running-validation.md).

## Execution boundaries

| Agent does | Agent does NOT |
| --- | --- |
| Read the integration code and the vendor API docs | Ask for or use 3rd-party vendor credentials |
| Write files under `integrations/<name>/validation/` | Change integration code, without telling the developer why |
| Mark every route it writes `verified: false` | Present made-up fixtures as recorded vendor responses |
| Run the scenarios and write the first expected entities | Commit expected entities without the developer's review |

## Steps

### 1. Understand the integration

Read `.port/spec.json`, `.port/resources/port-app-config.yaml`,
`.port/resources/blueprints.json`, the client and the exporters. Write down:
- The config key that sets the vendor base URL. If there is none, stop: the integration
  cannot be pointed at the mock. Tell the developer it needs a configurable base URL.
- Auth: which headers or query parameters the client sends.
- Per kind: the endpoints called, pagination style, and selector options.

### 2. Response models

For each endpoint, write a pydantic model in `validation/models/<resource>.py` from the
vendor's API docs. Put the docs URL in `source` and the endpoint in `endpoint`. Include
only fields the mappings or the client read, plus `id`-like fields.

### 3. Mock routes and bodies

- One route file per resource in `validation/mock/routes/<resource>.yaml`.
- Large or reused bodies go to `validation/mock/bodies/<resource>/`; small ones inline.
- Set `response_model` on every response and `verified: false` on every route.
- Match on what distinguishes requests: method, path, and the pagination query parameter.
  Don't match on auth header values.
- Use realistic but fake data: no real names, emails or tokens.
- Response bodies are not templated. If the client follows absolute "next page" URLs from
  the response body, tell the developer that pagination can't be mocked yet, and mock a
  single page instead.

### 4. Scenarios

Write `validation/scenarios.yaml`. Put the fake credentials and `{{mock_base_url}}` under
`defaults.integration_config`. Add only the scenarios that apply:

| Scenario | Covers |
| --- | --- |
| `happy_path` | Every kind, one or two pages |
| `<kind>_pagination` | The client walks all pages and stops |
| `<kind>_rate_limit` | A `sequence` with 429 and then 200; the resync still completes |
| `<kind>_empty` | An empty list; no entities and no errors |
| `<kind>_<selector>` | A selector variant via `port_app_config_overrides` |

### 5. Run and write expected entities

Run every scenario with the loop from the running reference (including mock port fallback
when 9000 is in use). The first run of a scenario reports `comparison.status: new` and
writes `validation/expected/<scenario>/`. Fix unmatched requests (a missing or wrong route)
and rerun until every scenario passes.

### 6. Summarize for review

Keep it short:
- Scenarios and what each covers.
- Endpoints mocked, with the docs URL each model came from.
- Assumptions made where the docs were unclear.
- Every route is `verified: false`. Expected entities should be reviewed before commit.
