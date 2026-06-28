# Mend

An integration used to import [Mend.io](https://www.mend.io/) projects and SCA security findings into Port, so engineering teams can see which services own vulnerable libraries, track remediation progress, and surface SCA risk alongside the rest of their software catalog.

## Overview

The integration polls the Mend Web Services API and produces two kinds of entities in Port:

| Kind            | Source endpoint                                                        | Blueprint     |
| --------------- | ---------------------------------------------------------------------- | ------------- |
| `mend-project`  | `POST /api/v3.0/orgs/{orgUuid}/projects/summaries`                     | `mendProject` |
| `sca-finding`   | `GET  /api/v3.0/projects/{projectUuid}/dependencies/findings/security` | `mendSCA`     |

Each `sca-finding` is related to a `mend-project` via the `project` relation, so you can drill from a project into its open dependency vulnerabilities in Port.

## Prerequisites

- **Mend Activation Key** — From Mend Instance get the Activation Key for the Port Integration.
- **Port credentials** — `clientId` and `clientSecret` from `Port → Builder → Credentials`.
- For local development: **Python 3.12+** and **Poetry** `>=1.0,<2.0`.

## Configuration

The integration is configured via standard Ocean environment variables. The Mend-specific settings sit under `OCEAN__INTEGRATION__CONFIG__*`.

### Required

| Variable                                              | Description                                                          |
| ----------------------------------------------------- | -------------------------------------------------------------------- |
| `OCEAN__PORT__CLIENT_ID`                              | Port API client ID.                                                  |
| `OCEAN__PORT__CLIENT_SECRET`                          | Port API client secret.                                              |
| `OCEAN__INTEGRATION__CONFIG__MEND_ACTIVATION_KEY`     | Mend Activation Key (base64).                                        |

### Optional

| Variable                                                          | Default                  | Description                                                                                                                                                       |
| ----------------------------------------------------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OCEAN__PORT__BASE_URL`                                           | `https://api.getport.io` | Override for non-default Port environments.                                                                                                                       |
| `OCEAN__INTEGRATION__IDENTIFIER`                                  | `mend`                   | Identifier registered for this integration instance on Port.                                                                                                      |
| `OCEAN__EVENT_LISTENER__TYPE`                                     | `POLLING`                | `POLLING`, `KAFKA`, or `WEBHOOKS_ONLY`. Mend currently has no first-class webhook support — keep on `POLLING`.                                                    |
| `OCEAN__SCHEDULED_RESYNC_INTERVAL`                                | (none)                   | Minutes between polls. Each tick does a **partial (delta) sync** by default (see [Sync model](#sync-model)).                                                      |
| `OCEAN__INITIALIZE_PORT_RESOURCES`                                | `true`                   | On first boot, create the blueprints and `port-app-config` defined under `.port/resources/`.                                                                      |
| `OCEAN__INTEGRATION__CONFIG__FULL_SYNC_INTERVAL_MINUTES`          | `720` (12 h)             | Interval between **forced full resyncs**. Bypasses the delta marker so finding-only changes (status, suppressions, manual edits) are caught. Set `0` to disable delta entirely. |
| `APPLICATION__LOG_LEVEL`                                          | `INFO`                   | `DEBUG` / `INFO` / `WARNING` / `ERROR`.                                                                                                                           |

### Example `.env`

```bash
# Port API
OCEAN__PORT__CLIENT_ID=<port_client_id>
OCEAN__PORT__CLIENT_SECRET=<port_client_secret>
OCEAN__PORT__BASE_URL=https://api.getport.io

# Integration identity
OCEAN__INTEGRATION__IDENTIFIER=mend

# Event listener — partial sync every 60 min,
# forced full sync every 12 h (720 min) on top of that
OCEAN__EVENT_LISTENER__TYPE=POLLING
OCEAN__SCHEDULED_RESYNC_INTERVAL=60
OCEAN__INITIALIZE_PORT_RESOURCES=true

# Mend
OCEAN__INTEGRATION__CONFIG__MEND_ACTIVATION_KEY=<mend_activation_key>
OCEAN__INTEGRATION__CONFIG__FULL_SYNC_INTERVAL_MINUTES=720

# Logging
APPLICATION__LOG_LEVEL=INFO
```

A complete annotated template is shipped as [`.env.example`](.env.example).

## Resources

### `mend-project` → `mendProject`

Each Mend project becomes a `mendProject` entity with the following properties (defined in [`.port/resources/blueprints.json`](.port/resources/blueprints.json)):

- `applicationName`, `applicationUuid`, `createdAt`, `lastScanned`, `languages`
- Severity rollups: `totalCritical`, `totalHigh`, `totalMedium`, `totalLow`
- Per-engine stat objects: `dependencyFindingStats`, `codeFindingStats`, `containerFindingStats`

`lastScanned` is `null` for projects that have never been scanned — Port treats `null` as "field unset" and skips date-time format validation for it.

### `sca-finding` → `mendSCA`

Each SCA security finding becomes a `mendSCA` entity, related to its project:

- Identification: `status`, `severity` (enum: CRITICAL/HIGH/MEDIUM/LOW), `description`, `componentName`, `componentType`, `type`
- Risk: `cvssType`, `cvssScore`, `epssScore`, `exploitMaturity`, `reachability`, `malicious`, `violations`
- Timeline: `publishDate`, `detectedAt`, `modifiedAt`
- Remediation: `topFix`, `cveLink`, `mendLink`
- Suppression metadata: `suppressionReason`, `suppressionDate`

Full mapping lives in [`.port/resources/port-app-config.yml`](.port/resources/port-app-config.yml).

#### `severity` selector filter

`sca-finding` accepts an optional `severity` filter so you only ingest findings above your team's threshold:

```yaml
resources:
  - kind: sca-finding
    selector:
      query: 'true'
      severity:
        - CRITICAL
        - HIGH
```

Allowed values: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`. Omit the field to ingest every severity.

## Sync model

The integration combines a fast **delta path** with a periodic **forced-full path** so that:

- ordinary polls stay cheap on Mend's API quota, and
- finding-only changes that don't move the parent project's timestamps still get reflected.

### Partial / delta sync (the default)

Each poll triggered by `OCEAN__SCHEDULED_RESYNC_INTERVAL`:

1. Fetches the list of projects from Mend.
2. Keeps only projects whose `statistics.LAST_SCAN.lastScanTime` **or** `creationDate` moved since the last successful sync.
3. For each changed project, paginates its SCA findings and yields them to Port.
4. On success, advances the "last successful sync" marker to the time the run started. If the run raises mid-way, the marker stays put — the next run re-fetches the missed window. No silent gaps.

The marker is process-local (lives in `mend/core/sync_state.py`) and resets on restart. A restart simply means the next run is a full sync.

### Forced full sync

`OCEAN__INTEGRATION__CONFIG__FULL_SYNC_INTERVAL_MINUTES` (default `720`) layers a periodic full sync on top of the delta cadence. When the elapsed time since the last successful full sync exceeds this interval, the next poll ignores the delta marker and fetches every finding for every project — picking up things like:

- A user marked a finding **Suppressed** without rescanning.
- A finding's status transitioned `IN_REVIEW → REMEDIATED`.
- A topFix was edited in Mend.

Set the value to `0` to make every poll a full sync (skip the optimization entirely).

### Project list is fetched at most once per resync

`MendProjectExporter.get_paginated_resources` is decorated with `@cache_iterator_result()`, so even though both the `mend-project` resync and the `sca-finding` resync need the project list, Mend is hit only once per resync event. The cache is scoped to the running event and discarded when it ends.

### Stale-entity deletion

`.port/resources/port-app-config.yml` ships with `entityDeletionThreshold: 0`. That means resync never deletes entities that weren't yielded during the run — important because the delta path intentionally skips most projects. If you want stale findings cleaned up automatically, raise the threshold (e.g. `0.5`) and ensure your forced-full interval is short enough to enumerate every finding before deletion runs.

## Authentication

The Mend Activation Key is itself a base64-encoded JWT that contains:

- `integratorEmail` — the user the integration logs in as.
- `userKey` — the long-lived secret used at login.
- `wsEnvUrl` — the Mend SaaS hostname for the tenant. The API base URL is derived as `https://api-{hostname}` (e.g. `wsEnvUrl=https://saas.mend.io` → `https://api-saas.mend.io`).
- `orgUuid` — the organization context for every API call.

On startup the integration:

1. Decodes the activation key (Caesar shift + reverse + base64 + JWT decode) — `mend/auth/activation_key.py`. A malformed key surfaces as a single `MendAuthenticationError("Provide a valid Mend Activation key. …")` rather than a raw decoder traceback.
2. `POST /api/v3.0/login` with `{integratorEmail, userKey}` → `refreshToken`.
3. `POST /api/v3.0/login/accessToken?orgUuid=…` with the `wss-refresh-token` header → `jwtToken` + `tokenTTL` (seconds).
4. Caches the JWT in memory until ~60 s before TTL expiry.

If a request hits `401` mid-flight, the token is invalidated and the request retries once with a fresh JWT. A persistent `401` after that retry is treated as a real auth failure and raised — `401` is not in the ignored-error list, since silently swallowing it would hide bad credentials.

## Local development

```bash
cd integrations/mend
make install
cp .env.example .env
# fill in OCEAN__PORT__CLIENT_ID, OCEAN__PORT__CLIENT_SECRET,
#         OCEAN__INTEGRATION__CONFIG__MEND_ACTIVATION_KEY

make run            # starts the integration
make lint           # mypy + ruff + black + yamllint
make test           # pytest
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for deeper notes on the auth flow, pagination semantics, and gotchas.

## API documentation

- Mend API: https://api-docs.mend.io/platform/3.0
- Endpoints in use:
  - `POST /api/v3.0/login`
  - `POST /api/v3.0/login/accessToken`
  - `POST /api/v3.0/orgs/{orgUuid}/projects/summaries`
  - `GET  /api/v3.0/projects/{projectUuid}/dependencies/findings/security`

#### Develop & improve the integration — [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)
