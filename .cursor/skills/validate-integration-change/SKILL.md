---
name: validate-integration-change
description: Validate an Ocean integration by running mock-backed validation scenarios against Port and explaining the results. Use when the developer asks to validate, verify, trust local runs, or check an integration change. If validation/ is missing, bootstrap it automatically (see create-integration-validation) then run scenarios. Requires the integration name (folder under integrations/).
---

# Validate Integration Change

Run an integration's validation scenarios against the mock vendor API and a real Port
org, then tell the developer what changed and what to do about it.

Running the scenarios is described in
[references/running-validation.md](references/running-validation.md). Read it first.

## Execution boundaries

| Agent does | Agent does NOT |
| --- | --- |
| Bootstrap `validation/` when missing (full create-integration-validation flow), then run the mock and scenarios | Stop with "use create-integration-validation" instead of scaffolding |
| Run the mock and the scenarios | Ask for or use 3rd-party vendor credentials |
| Add missing mock routes, bodies and models marked `verified: false` | Change integration code to make validation pass |
| Explain entity diffs | Run `--update-expected` without the developer's approval |
| Report Port leftovers | Delete Port resources by hand |

## Steps

### 1. Scope and bootstrap

Determine the integration name (`integrations/<name>/`).

**Missing validation (automatic):** If `integrations/<name>/validation/scenarios.yaml` is
missing, or preflight would fail because `validation/` or `validation/mock/` does not exist,
do not stop or only suggest another skill. Read and execute
[create-integration-validation](../create-integration-validation/SKILL.md) end to end for that
integration (models, mock routes, `scenarios.yaml`, first scenario runs and expected
entities). Then continue with steps 2–5 below in the same session.

Stop without scaffolding only when create-integration-validation would stop anyway (for
example no configurable vendor base URL in spec — tell the developer what integration change
is required first).

**Scenario selection:** Read `git diff` for the integration when present. Note which kinds,
endpoints and mappings changed, then pick the scenarios whose `kinds` or `routes` cover them.
Run all scenarios when the change is broad (client, auth, pagination, `port-app-config.yml`).
When bootstrapping new validation, run every scenario defined in `scenarios.yaml`.

### 2. Preflight

Check the prerequisites in the reference. Stop and tell the developer what is missing.

### 3. Run

Run the loop from the reference, one scenario at a time. If port 9000 is busy, start the
mock on the next free port (9001, 9002, …) per the reference, pass `--mock-base-url` on
every `make validate`, and use that base URL for admin `curl`s. Always stop the mock process
you started at the end.

### 4. Act on each report

| Report says | Do |
| --- | --- |
| `status: error` | Setup problem. Show `error` and stop. |
| `integration.returncode` not 0, or `timed_out` | Read `stderr_tail`. Code bug: report it. Config bug in the scenario: fix it and rerun. |
| `unmatched_requests` | The change calls an endpoint the mock lacks. Add a model, route and body following `create-integration-validation`, mark the route `verified: false`, reload the scenario and rerun. |
| `comparison.status: different` | Explain each `entity_diff` entry and whether the change intended it. Ask before rerunning with `--update-expected`. |
| `comparison.status: skipped` | The resync did not complete. Read `resync_status` and `stderr_tail`. |
| `port.cleanup_leftovers` | List what is left in Port so the developer can delete it. |

### 5. Summarize

Keep it short:
- If validation was bootstrapped in this session, say so briefly (scenarios added, not a
  separate manual step).
- One line per scenario: passed or failed, and why.
- Fixtures you added (all `verified: false`) and what they assume about the vendor API.
- Changes to expected entities that need the developer's approval.
- Port leftovers, if any.
