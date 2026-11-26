---
name: validate-integration-change
description: Validate an Ocean integration with mock-backed scenarios against Port, and create those scenarios when they don't exist yet (validation/ folder with response models, mock routes, scenarios.yaml and expected entities). Use when the developer asks to validate, verify, trust local runs or check an integration change, or to add validation, mock scenarios or validation fixtures to an integration. Requires the integration name (folder under integrations/).
---

# Validate Integration Change

Run an integration's validation scenarios against the mock vendor API and a real Port
org, then tell the developer what changed and what to do about it. If the integration has
no validation yet, build it first.

Running the scenarios is described in
[references/running-validation.md](references/running-validation.md). Read it first.
Building `validation/` from scratch is described in
[references/bootstrapping-validation.md](references/bootstrapping-validation.md).

## Execution boundaries

| Agent does | Agent does NOT |
| --- | --- |
| Read the integration code and the vendor API docs | Ask for or use 3rd-party vendor credentials |
| Write files under `integrations/<name>/validation/` | Change integration code to make validation pass, or without telling the developer why |
| Mark every route it writes `verified: false` | Present made-up fixtures as recorded vendor responses |
| Run the mock and the scenarios, and explain entity diffs | Run `--update-expected` without the developer's approval |
| Preflight mandatory `OCEAN__*` env keys (names only) before the mock | Start `validate-mock` or `make validate` when Port env is incomplete |
| Write the first expected entities for new scenarios | Commit expected entities without the developer's review |
| Report Port leftovers | Delete Port resources by hand |

## Steps

### 1. Scope

Determine the integration name (`integrations/<name>/`).

**No validation yet:** If `integrations/<name>/validation/scenarios.yaml` or
`validation/mock/` is missing, or the developer asked to add validation, follow
[references/bootstrapping-validation.md](references/bootstrapping-validation.md), then
continue with step 2. Stop only where that reference says to (for example, no configurable
vendor base URL), and tell the developer what integration change is needed first.

**Scenario selection:** Read `git diff` for the integration when present. Note which kinds,
endpoints and mappings changed, then pick the scenarios whose `kinds` or `routes` cover them.
Run all scenarios when the change is broad (client, auth, pagination, `port-app-config.yml`)
or when validation was just bootstrapped.

### 2. Preflight

Run this **before** mock port selection, `validate-mock`, or `make validate`.

1. **Mandatory environment** — follow
   [references/running-validation.md](references/running-validation.md) (*Mandatory
   environment*). If any required `OCEAN__*` keys are missing or empty, list **only the key
   names**, say they belong in `integrations/<name>/.env` (or the shell), and **stop**. Do not
   start the mock or validation loop until the developer confirms env is ready, unless they
   explicitly ask to continue anyway.
2. **Tooling** — repo root `.venv/` and the integration venv (`make install` in
   `integrations/<name>/`). Stop and name what is missing.

Never read or print credential values. Vendor API secrets are not required for mock-backed
validation when `scenarios.yaml` supplies `integration_config`.

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
| `unmatched_requests` | The integration calls an endpoint the mock lacks. Add a model, route and body following the bootstrapping reference (steps 2 and 3), reload the scenario and rerun. |
| `comparison.status: new` | First run of a scenario; expected entities were written. Flag them for review. |
| `comparison.status: different` | Explain each `entity_diff` entry and whether the change intended it. Ask before rerunning with `--update-expected`. |
| `comparison.status: skipped` | The resync did not complete. Read `resync_status` and `stderr_tail`. |
| `port.cleanup_leftovers` | List what is left in Port so the developer can delete it. |

### 5. Summarize

Keep it short:
- One line per scenario: passed or failed, and why.
- If validation was bootstrapped: scenarios and what each covers, endpoints mocked with the
  docs URL each model came from, and assumptions made where the docs were unclear.
- Fixtures you added (all `verified: false`) and what they assume about the vendor API.
- Expected entities that are new or changed and need the developer's review.
- Port leftovers, if any.
