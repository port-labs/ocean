# Plain

Ocean integration that syncs [Plain](https://www.plain.com/) support data into Port.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)

## Kinds

| Kind | Plain query | Permission |
|------|-------------|------------|
| `company` | `companies` | `company:read` |
| `tenant` | `tenants` | `tenant:read` |
| `user` | `users` | `user:read` |
| `customer` | `customers` | `customer:read` |
| `thread` | `threads` | `thread:read` |

Mappings live in `.port/resources/port-app-config.yml`. Blueprints are `plainCompany`, `plainTenant`, `plainUser`, `plainCustomer`, and `plainThread`. A thread assignee relation is set only when `assignedTo` is a `User`. Customer tenants come from `tenantMemberships`.

Create the API key on a Plain machine user (Settings → Machine Users → Add API key). The token looks like `plainApiKey_…`.

## Install configuration

| Spec name | Required | Default | Purpose |
|-----------|----------|---------|---------|
| `apiToken` | yes | | Bearer token for the GraphQL API |
| `apiUrl` | no | `https://core-api.uk.plain.com/graphql/v1` | GraphQL endpoint |
| `pageSize` | no | `100` | List page size. Plain's maximum is 100 |
| `threadStatusFilter` | no | unset | Comma-separated statuses: `TODO`, `SNOOZED`, `DONE`. Omit to sync every status |
| `enableLiveEvents` | no | `false` | Reserved for webhook registration. Leave false |

For local runs, set the same values as environment variables, for example `OCEAN__INTEGRATION__CONFIG__API_TOKEN`. See `.env.example`.

## Limitations

- Live events are off by default. Turning `enableLiveEvents` on does not register webhooks yet; that lands in Phase 2.
- Only the UK GraphQL host is known to resolve. `apiUrl` is an override if Plain adds another region.
- Customer tenants come from the first page of `tenantMemberships` (at most 100). That selection needs `customerTenantMembership:read` in addition to `customer:read`.
- The user query selects `role`, which needs `roles:read` in addition to `user:read`.
- Company fields are `id`, `name`, and `domainName`. Company has no `externalId`.
- A thread assignee is a `User`, `MachineUser`, or `System`. The sync stores `__typename` and `id` for those three.
- HTTP failures (including a missing token) raise before GraphQL parsing. A GraphQL `errors` array fails the sync instead of yielding an empty page.
