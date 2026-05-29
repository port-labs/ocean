# Contributing to Ocean - mend

## Running locally

### Prerequisites

- Python 3.12+
- Poetry (`pip install 'poetry>=1.0.0,<2.0.0'`)
- A Mend.io account with an **Activation Key** (Mend → User Profile → User Keys → Activation Key)
- Port credentials (`clientId`, `clientSecret`) — Port → Builder → Credentials

### Setup

```bash
cd integrations/mend
make install
cp .env.example .env
# Edit .env and fill in:
#   OCEAN__PORT__CLIENT_ID
#   OCEAN__PORT__CLIENT_SECRET
#   OCEAN__INTEGRATION__CONFIG__MEND_ACTIVATION_KEY
```

### Run

```bash
make run            # starts the integration with the local .env config
```

Or with the Ocean CLI directly:

```bash
ocean sail
```

### Lint & test

```bash
make lint           # mypy + ruff + black + yamllint
make test           # pytest
```

## How the integration works

- **Auth** — the activation key is a base64-encoded JWT containing `integratorEmail`, `userKey`, `wsEnvUrl`, and `orgUuid`. The authenticator decodes it, calls `/api/v3.0/login` to get a refresh token, then `/api/v3.0/login/accessToken` to get a JWT used as a Bearer token. Tokens are held in process memory and refreshed on TTL expiry or on the first 401 response.
- **Resync flow** — two kinds:
  - `mend-project` — paginates `/api/v3.0/orgs/{orgUuid}/projects/summaries` (POST).
  - `sca-finding` — for each project, paginates `/api/v3.0/projects/{projectUuid}/dependencies/findings/security`.
- **Delta sync** — `on_security_finding_resync` skips projects whose `lastScanTime` / `creationDate` did not change since the last successful sync. The marker is process-local (resets on restart) and is **only advanced after the resync iterates every project without raising**. If a run fails partway through (network error, Mend 5xx, etc.), the marker is left untouched so the next run re-fetches the missed projects rather than leaving silent gaps.
- **Forced full sync** — `OCEAN__INTEGRATION__CONFIG__FULL_SYNC_INTERVAL_MINUTES` (default `720`) periodically bypasses the delta marker so finding-only changes (status updates, suppressions) are picked up. Set to `0` to make every poll a full sync. The full-sync marker follows the same all-or-nothing rule: a failed full sync does not push the next forced-full window forward.
- **Project list caching** — `MendProjectExporter.get_paginated_resources` is wrapped with `@cache_iterator_result()`, so the project list is fetched from Mend at most once per resync event even though both kinds read it.

## Gotchas

- Mend's organization API base URL is derived from `wsEnvUrl` inside the activation key (`https://api-{hostname}`); do not hardcode it.
- The Mend API uses cursor-based (not offset-based) pagination. `cursor` is omitted on the first page; the response's `additionalData.cursor` feeds the next request, and pagination stops when `additionalData.next` is null.
- Default `entityDeletionThreshold` is set to `0` in `.port/resources/port-app-config.yml` so delta resyncs don't delete findings from projects that weren't touched in the current run. If you want stale findings to be cleaned up, raise this threshold and keep the `OCEAN__INTEGRATION__CONFIG__FULL_SYNC_INTERVAL_MINUTES` to `0`.
- Persistent 401s (after one auto-retry with a refreshed token) are propagated as errors — Mend won't recover from genuinely bad credentials.
