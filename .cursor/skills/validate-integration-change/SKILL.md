---
name: validate-integration-change
description: Validate a change to an Ocean integration by running its mock-backed validation scenarios against Port and explaining the results. Use when the developer asks to validate, verify or check an integration change, or after changing an integration that has a validation/ folder. Requires the integration name (folder under integrations/).
---

# Validate Integration Change

Run an integration's validation scenarios against the mock vendor API and a real Port
org, then tell the developer what changed and what to do about it.

Running the scenarios is described in
[references/running-validation.md](references/running-validation.md). Read it first.

## Execution boundaries

| Agent does | Agent does NOT |
| --- | --- |
| Run the mock and the scenarios | Ask for or use 3rd-party vendor credentials |
| Add missing mock routes, bodies and models marked `verified: false` | Change integration code to make validation pass |
| Explain entity diffs | Run `--update-expected` without the developer's approval |
| Report Port leftovers | Delete Port resources by hand |

## Steps

### 1. Scope

- If `integrations/<name>/validation/scenarios.yaml` does not exist, stop and suggest the
  `create-integration-validation` skill.
- Read `git diff` for the integration. Note which kinds, endpoints and mappings changed,
  then pick the scenarios whose `kinds` or `routes` cover them. Run all scenarios when
  the change is broad (client, auth, pagination, `port-app-config.yml`).

### 2. Preflight

Check the prerequisites in the reference. Stop and tell the developer what is missing.

### 3. Run

Run the loop from the reference, one scenario at a time. Always stop the mock at the end.

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
- One line per scenario: passed or failed, and why.
- Fixtures you added (all `verified: false`) and what they assume about the vendor API.
- Changes to expected entities that need the developer's approval.
- Port leftovers, if any.
