# Sonatype Lifecycle

A [Port Ocean](https://ocean.port.io/) integration that ingests software
composition data from **Sonatype Lifecycle (Nexus IQ Server)** into your Port
software catalog.

It maps your Sonatype hierarchy — organizations, applications, their latest
Application Composition Reports per lifecycle stage, and the individual policy
violations found in those reports — into Port entities, and keeps them up to
date both on a schedule and in real time via Sonatype webhooks.

## What gets synced

| Kind | Blueprint | Source in Sonatype IQ |
| --- | --- | --- |
| `organization` | `sonatypeOrganization` | `GET /api/v2/organizations` |
| `application` | `sonatypeApplication` | `GET /api/v2/applications` |
| `sourceControl` | `sonatypeApplication` (upsert) | `GET /api/v2/sourceControl/application/{id}` |
| `report` | `sonatypeReport` | `GET /api/v2/reports/applications/{id}` (one entity per stage) |
| `policyViolation` | `sonatypePolicyViolation` | `{reportDataUrl}/policy` |
| `component` | `sonatypeComponent` | `{reportDataUrl}/raw` (+ Component Remediation API for fix versions) |
| `vulnerability` | `sonatypeVulnerability` | `{reportDataUrl}/raw` → `securityData.securityIssues` (deduped CVEs) |

Relations: `policyViolation → report → application → organization`, and
`component → application/report` with `component → vulnerability` (many).
`sourceControl` upserts the same `sonatypeApplication` entity to set
`githubRepository` (when IQ SCM is configured for GitHub).
Components carry Sonatype's **recommended upgrade version** (`recommendedVersion`)
when remediation lookups are enabled.

To connect Sonatype applications to your existing Port `service` blueprint, see
[`.port/resources/examples/link-applications-to-services.yaml`](./.port/resources/examples/link-applications-to-services.yaml).

## Prerequisites

- A running Sonatype IQ Server (self-hosted) or a Sonatype Cloud tenant.
- A user account (ideally a dedicated service account) with permission to view
  the organizations and applications you want to sync. A **user token** for that
  account is recommended over a password
  ([how to create one](https://help.sonatype.com/en/user-tokens.html)).
- A Port account and a Port API client ID/secret.

## Configuration

| Parameter | Required | Description |
| --- | --- | --- |
| `iqServerUrl` | ✅ | Base URL of IQ Server, e.g. `https://iq.example.com` |
| `iqUsername` | ✅ | Username / service account |
| `iqUserToken` | ✅ | User token (or password) for that account |
| `webhookSecret` | ➖ | Shared secret matching the IQ webhook "Secret Key"; enables HMAC-SHA1 verification of live events |
| `appHost` | ➖ | Public base URL of this integration; used to print the exact webhook target to register |

## Running locally

```bash
# From the integration directory
poetry install

# Provide configuration via environment variables
export OCEAN__PORT__CLIENT_ID="<your-port-client-id>"
export OCEAN__PORT__CLIENT_SECRET="<your-port-client-secret>"
export OCEAN__INTEGRATION__CONFIG__IQ_SERVER_URL="https://iq.example.com"
export OCEAN__INTEGRATION__CONFIG__IQ_USERNAME="svc-port"
export OCEAN__INTEGRATION__CONFIG__IQ_USER_TOKEN="<user-token>"

# Run a one-off sync
ocean sail
```

## Enabling real-time updates (webhooks)

Sonatype IQ Server does not expose a REST endpoint for creating webhooks, so the
webhook is registered once, manually, in the IQ admin UI:

1. In IQ Server go to **System Preferences → Webhooks → New Webhook**.
2. Set the **URL** to `<appHost>/integration/webhook`.
3. (Recommended) Set a **Secret Key** and put the same value in the
   `webhookSecret` configuration so events are verified.
4. Enable the **Application Evaluation** and **Policy Management** event types.

Application Evaluation events refresh the affected report and its policy
violations; Policy Management events refresh the affected application or
organization.

## Development

```bash
poetry install
poetry run pytest            # run the test suite
poetry run ruff check .      # lint
poetry run mypy .            # type-check
```

See [`WALKTHROUGH.md`](./WALKTHROUGH.md) for a full description of how the
integration was built, step by step.

# Self-service actions

These two JSON files are exported, ready-to-use definitions of this
integration's self-service actions. They are **optional** and not created
automatically — Ocean's resource scaffolding (`.port/resources/blueprints.json`,
`.port/resources/port-app-config.yaml`) only provisions blueprints and data
mapping, not actions, so bringing these in is a deliberate opt-in step you
take if/when you want them.

## Adding an action to your Port organization

1. Go to the **Self-service** page in Port.
2. Click **+ New Action** → **{...} Edit JSON**.
3. Paste the contents of the JSON file you want (see placeholders below —
   fill those in first, or edit them afterwards in the UI).
4. Click **Create**.

Repeat for the other file if you want both. There's no dependency between
them — take either one independently.

## Prerequisites

Both actions assume the blueprint/mapping setup this integration provisions
is already in place, plus two extra pieces that live on top of it:

- **`sonatypeApplication.githubRepository`** relation and **`sonatypeComponent.repositoryIdentifier`**
  mirror property (`application.githubRepository.$identifier`) — these are
  what let `upgrade_component_to_recommended_version` auto-select the target
  repo. They're populated from the `sourceControl` kind, so a repository is
  only pre-filled for applications that actually have Source Control
  Management configured in IQ Server.
- The **GitHub Ocean/GitHub App integration** installed, with a
  `githubRepository` blueprint present — `upgrade_component_to_recommended_version`'s
  `target_repository` input targets that blueprint. Without it installed,
  the action will still import, but the input will have nothing to pick
  from.

## Placeholders you need to fill in before these are usable

### `request_policy_violation_waiver.json`
- `REPLACE_WITH_YOUR_IQ_SERVER_BASE_URL` in `invocationMethod.url` — your
  actual IQ Server host.
- IQ's Policy Waiver Request API uses basic auth. Add an `Authorization`
  header to `invocationMethod.headers` sourced from a Port secret (Settings
  → Credentials → Secrets), e.g. `"Authorization": "Basic {{ .secrets._IQ_BASIC_AUTH }}"`.
- If IQ Server is on-prem and not reachable from Port's SaaS webhook egress,
  point the URL at a relay (e.g. an n8n workflow or small Lambda) that
  forwards to IQ instead of calling it directly.

### `upgrade_component_to_recommended_version.json`
- `<AUTOMATION_GITHUB_ORG>` / `<AUTOMATION_GITHUB_REPO>` in
  `invocationMethod.url` — the GitHub org/repo that hosts your
  `upgrade-component-version.yml` workflow (you provide this; it is not
  shipped with the integration). The workflow must accept the inputs listed
  in the action's `invocationMethod.body.inputs`.
- Port secret `_GITHUB_TOKEN` — a token with `Actions: write` on that
  automation repo, so Port can dispatch the workflow.
- In the automation repo itself: a `GH_PAT` secret with `Contents` + `Pull
  requests` write access on whichever repos the upgrade PRs will target
  (the default `GITHUB_TOKEN` can't push cross-repo).

## Permissions

Neither JSON file sets custom execute/approve permissions — both import
with Port's default (organization admins can approve/execute). If you want
non-admins to request waivers with a specific approver group, or want to
restrict who can trigger the upgrade action, set that up afterwards in the
Self-service page → action → Permissions tab, or via the
[update an action's permissions API](https://docs.port.io/api-reference/update-an-actions-permissions).
This isn't exported here because permissions are org-specific by nature.
