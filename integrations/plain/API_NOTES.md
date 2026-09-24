# Plain API verification (T0)

Verified **2026-09-24** against:

- [GraphQL introduction](https://www.plain.com/docs/graphql/introduction)
- [Authentication](https://www.plain.com/docs/graphql/authentication)
- [Pagination](https://www.plain.com/docs/graphql/pagination)
- Public schema: `GET https://core-api.uk.plain.com/graphql/v1/schema.graphql` (HTTP 200, `content-type: text/plain`, 631249 bytes)

Live calls used `PLAIN_TOKEN` from `integrations/plain/.env` (gitignored). Unauthenticated probes are recorded under Auth. Sanitized `threads` and `companies` pages are at the bottom.

## Endpoint

| Item | Finding |
|------|---------|
| URL | `https://core-api.uk.plain.com/graphql/v1` |
| Method | `POST` |
| Body | JSON: `query`, `variables`, optional `operationName` (tracking only) |
| Headers | `Content-Type: application/json` and `Authorization: Bearer <api key>` |
| Regional variants | Not documented. `core-api.us.plain.com` and `core-api.eu.plain.com` do not resolve. Use the UK URL; keep `apiUrl` overridable in spec only as an escape hatch. |
| Schema | Public, no auth: `https://core-api.uk.plain.com/graphql/v1/schema.graphql` |

API keys are created on a machine user (Settings → Machine Users → Add API key). Docs show the token form `plainApiKey_…`.

## Auth

Missing or invalid bearer is rejected at the gateway **before** GraphQL parsing.

Captured 2026-09-24 (sanitized; no token sent):

```http
POST /graphql/v1 HTTP/2
Host: core-api.uk.plain.com
Content-Type: application/json

{"query":"query ListThreads($first: Int) { threads(first: $first) { totalCount pageInfo { hasNextPage endCursor } edges { node { id ref title status priority } } } }","variables":{"first":1},"operationName":"ListThreads"}
```

```http
HTTP/2 401
content-type: application/json

{"message":"Unauthorized"}
```

The same body is returned for `companies` with no `Authorization` header, for a bogus `Bearer not-a-real-key`, and for `GET` on the GraphQL URL. The client must treat non-2xx responses as HTTP failures. Do not assume an `errors[]` array on 401.

GraphQL failures on an authorized call are a separate path: HTTP 200 with a top-level `errors` array (standard GraphQL). Insufficient permission should name the missing permission (per Plain’s auth docs).

## Pagination

Relay cursor pagination. From the pagination doc:

- Default page size **25**
- Maximum page size **100**
- Forward: `first` + `after`
- Backward: `last` + `before`
- Mixing directions (`first` with `before`, or `last` with `after`) is a validation error

`PageInfo`:

```graphql
type PageInfo {
  hasPreviousPage: Boolean!
  hasNextPage: Boolean!
  startCursor: String
  endCursor: String
}
```

Phase 1 should page forward only: pass `first` (capped at 100) and `after` = previous `pageInfo.endCursor`, stop when `hasNextPage` is false.

`totalCount` is **not** on every connection:

| Connection | `edges` / `pageInfo` | `totalCount` |
|------------|----------------------|--------------|
| `ThreadConnection` | yes | yes |
| `CustomerConnection` | yes | yes |
| `CompanyConnection` | yes | no |
| `TenantConnection` | yes | no |
| `UserConnection` | yes | no |

There is no `nodes` shortcut. Read `edges { cursor node }`.

## List queries

All five are root `Query` fields. Connection path for the paginator is `data.<field>`.

| Kind | Field | Permission | Connection path |
|------|--------|------------|-----------------|
| company | `companies` | `company:read` | `data.companies` |
| tenant | `tenants` | `tenant:read` | `data.tenants` |
| user | `users` | `user:read` | `data.users` |
| customer | `customers` | `customer:read` | `data.customers` |
| thread | `threads` | `thread:read` | `data.threads` |

Argument shapes from the schema (2026-09-24):

```graphql
companies(first: Int, after: String, last: Int, before: String, filters: CompaniesFilter): CompanyConnection!
tenants(first: Int, after: String, last: Int, before: String, filters: TenantsFilter): TenantConnection!
users(filters: UsersFilter, first: Int, after: String, last: Int, before: String): UserConnection!
customers(filters: CustomersFilter, sortBy: CustomersSort, first: Int, after: String, last: Int, before: String): CustomerConnection!
threads(filters: ThreadsFilter, sortBy: ThreadsSort, first: Int, after: String, last: Int, before: String): ThreadConnection!
```

`ThreadsFilter.statuses` is `[ThreadStatus!]`. Status enum: `TODO`, `SNOOZED`, `DONE`. That is the variable for an optional `threadStatusFilter`.

### Field corrections vs the implementation plan

These matter when writing queries. Several plan field names do not exist on the schema.

- **Timestamps** are objects, not scalars: `DateTime { unixTimestamp iso8601 }`. Select `createdAt { iso8601 }` (and the same for `updatedAt`).
- **Company** has `id`, `name`, `domainName` (not `domain`). There is **no** `externalId`.
- **Tenant** has `id`, `name`, `externalId: String!`, `url`, `createdAt`, `updatedAt`.
- **User** has `id`, `fullName`, `publicName`, `email: String!`, `status: UserStatus!` (`ONLINE`, `OFFLINE`, `AWAY`; `BREAK` is deprecated), `role { id name key }`. No `externalId`.
- **Customer.email** is `EmailAddress { email isVerified verifiedAt }`, not a string.
- **Customer → company** is `company { id }`.
- **Customer → tenants** is not `tenants[]`. It is the nested connection `tenantMemberships { edges { node { tenant { id } } } }`.
- **Thread.assignedTo** is the union `ThreadAssignee = User | MachineUser | System`. Use an inline fragment and treat assignee as a user only when `__typename` is `User`.
- **Thread.priority** is `Int` (0 urgent, 1 high, 2 normal, 3 low), not an enum.
- **Thread.tenant** is a nullable `Tenant`. **Thread.customer** is a required `Customer`.

Minimal list selections to use in T5–T9 (pagination args omitted):

```graphql
companies { edges { node { id name domainName createdAt { iso8601 } updatedAt { iso8601 } } } }
tenants { edges { node { id externalId name createdAt { iso8601 } updatedAt { iso8601 } } } }
users { edges { node { id fullName email status role { id name key } } } }
customers { edges { node {
  id externalId fullName
  email { email }
  company { id }
  tenantMemberships(first: 100) { edges { node { tenant { id } } } }
} } }
threads { edges { node {
  id ref externalId title status priority
  customer { id }
  tenant { id }
  assignedTo { __typename ... on User { id } }
} } }
```

`tenantMemberships` and any other nested connection are themselves capped at 100. Phase 1 can take the first page; do not assume a customer has at most 100 tenants without a follow-up if that matters.

## Single-entity queries (Phase 2 stubs)

Both exist. Argument name is `<entity>Id`, not `id`.

```graphql
thread(threadId: ID!): Thread          # permission thread:read; null if missing
customer(customerId: ID!): Customer    # permission customer:read; null if missing
```

Also present, if later stubs want them: `company(companyId: ID!)`, `tenant(tenantId: ID!)`, `user(userId: ID!)`.

## API key permissions (Phase 1)

Exact strings from schema field descriptions:

- `company:read`
- `tenant:read`
- `user:read`
- `customer:read`
- `thread:read`

Create the machine-user key with those five. Webhook registration is out of scope here; it will need its own permissions in Phase 2.

The key in `integrations/plain/.env` (`PLAIN_TOKEN`, gitignored) was checked with `myPermissions` on 2026-09-24. All five are present.

## Live list pages

Captured 2026-09-24 with `curl` against the UK endpoint, `first: 1`, Bearer token from `integrations/plain/.env`. Both returned HTTP 200 and `data` with no `errors`. Identifiers, names, titles, and cursors below are redacted.

`threads`:

```json
{
  "data": {
    "threads": {
      "totalCount": 221,
      "pageInfo": { "hasNextPage": true, "endCursor": "<redacted-cursor>" },
      "edges": [
        {
          "node": {
            "id": "<id>",
            "ref": "<ref>",
            "title": "<title>",
            "status": "TODO",
            "priority": 3,
            "externalId": null,
            "customer": { "id": "<id>" },
            "tenant": null,
            "assignedTo": null
          }
        }
      ]
    }
  }
}
```

`companies` (no `totalCount` on this connection):

```json
{
  "data": {
    "companies": {
      "pageInfo": { "hasNextPage": true, "endCursor": "<redacted-cursor>" },
      "edges": [
        {
          "node": {
            "id": "<id>",
            "name": "<name>",
            "domainName": "<domainName>",
            "createdAt": { "iso8601": "<redacted-timestamp>" },
            "updatedAt": { "iso8601": "<redacted-timestamp>" }
          }
        }
      ]
    }
  }
}
```

A client with an empty `User-Agent` was rejected by Cloudflare with HTTP 403 and body `error code: 1010`. `curl`’s default user agent and a short browser user agent both succeeded. The Ocean HTTP client should send a non-empty `User-Agent`.
