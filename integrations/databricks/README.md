# Databricks

An integration used to import Databricks resources into Port.

Each integration instance targets a single Databricks workspace (`workspaceUrl`). It supports:

- **Compute & Jobs**: `clusters`, `jobs`, `job_runs`, `pipelines` (Delta Live Tables), `sql_warehouses`
- **Unity Catalog**: `catalogs`, `schemas`, `tables`

## Authentication

Configure either:

- `token`: a Databricks personal access token (PAT), or
- `clientId` + `clientSecret`: a Databricks service principal used for OAuth machine-to-machine (M2M) authentication

If `token` is set it takes precedence. OAuth M2M access tokens are cached and refreshed automatically before they expire.

## Live updates

Only `jobs` and `job_runs` receive live webhook updates; every other resource kind is resync-only.

When a base URL is configured (via `OCEAN__BASE_URL`, or the legacy `appHost` config, and the event listener
is not `ONCE`), the integration registers a Databricks notification destination of type webhook pointing at
`<baseUrl>/integration/webhook` on startup. To receive live job run updates, point your Databricks job's
notification settings at that registered destination.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/data-engineering/databricks)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)
