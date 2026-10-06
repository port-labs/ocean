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
| `machine-user` | `machineUsers` | likely `machineUser:read` (confirm on your API key) |
| `customer` | `customers` | `customer:read` |
| `thread` | `threads` | `thread:read` |
| `thread-message` | `thread.timelineEntries` | `timeline:read` |
| `discussion` | `discussions` filtered by thread | not named in the public schema |
| `discussion-message` | `discussion.messages` | not named in the public schema |

Mappings live in `.port/resources/port-app-config.yml`. Blueprints are `plainCompany`, `plainTenant`, `plainUser`, `plainMachineUser`, `plainCustomer`, `plainThread`, `plainThreadMessage`, `plainDiscussion`, and `plainDiscussionMessage`. A thread `assignee` relation is set only when `assignedTo` is a `User`; a `machineAssignee` relation is set when it is a `MachineUser`. Thread tier is synced as a string property (`.tier.name`), not a separate kind. Machine users sync all by default (including deleted); set `excludeDeleted: true` on the machine-user selector to skip deleted ones at sync time, or keep them and filter in Port with a query such as `.isDeleted == false`. Customer tenants come from `tenantMemberships`. On the thread, thread-message, discussion, and discussion-message selectors, `excludeDoneThreads: true` syncs only `TODO` and `SNOOZED` threads. `false` syncs every status. On discussion and discussion-message, `excludeAiDiscussions: true` skips Cursor and agent-session discussions (and their messages) at fetch time; `false` syncs every discussion including AI ones. Each flag is independent. The next resync uses the saved mapping. Thread messages are timeline entries that have text. Discussions are the internal conversations on those threads. A discussion message is related to its discussion and to the parent thread. Slack links and email recipients are stored when Plain sends them.

Create the API key on a Plain machine user (Settings → Machine Users → Add API key). The token looks like `plainApiKey_…`.

## Install configuration

| Spec name | Required | Default | Purpose |
|-----------|----------|---------|---------|
| `apiToken` | yes | | Bearer token for the GraphQL API |
| `apiUrl` | no | `https://core-api.uk.plain.com/graphql/v1` | GraphQL endpoint |
| `pageSize` | no | `100` | List page size. Plain's maximum is 100 |
| `threadStatusFilter` | no | unset | Comma-separated statuses (`TODO`, `SNOOZED`, `DONE`) for a thread fetch that does not receive a status list. Thread resync uses `excludeDoneThreads` on the thread selector |
| `enableLiveEvents` | no | `false` | When true, registers a Plain webhook target at `{OCEAN__BASE_URL}/integration/webhook` |
| `webhookSecret` | no | unset | Workspace HMAC secret (Settings → Request signing). Verifies `Plain-Request-Signature` |

For local runs, set the same values as environment variables, for example `OCEAN__INTEGRATION__CONFIG__API_TOKEN`. See `.env.example`.

## Live events

Set `enableLiveEvents: true`, configure `OCEAN__BASE_URL`, and optionally `webhookSecret`. On start the integration creates or updates a Plain webhook target (needs `webhookTarget:create` / `webhookTarget:edit` / `webhookTarget:read`). If the API key cannot create the target, startup still succeeds and inbound events on `{OCEAN__BASE_URL}/integration/webhook` are processed — create the webhook target in Plain yourself.

| Kind | Live-event source |
|------|-------------------|
| `thread` | `thread.thread_*` (created, status, assignment, labels, fields, tenant, locked, …) |
| `customer` | `customer.customer_created` / `updated` / `deleted` / `changed` |
| `thread-message` | Channel/timeline events (`thread.email_received`, `timeline.timeline_entry_changed`, …) |
| `discussion` | `discussion.discussion_created`, `discussion.message_created`, approval events |
| `discussion-message` | `discussion.message_created` |
| `company` | No `company.*` webhooks — refreshed from customer create/update events |
| `tenant` | No `tenant.*` webhooks — refreshed from `thread.thread_tenant_updated` |
| `user` | No `user.*` webhooks — refreshed from `thread.thread_assignment_transitioned` when the assignee is a human user |
| `machine-user` | No `machineUser.*` webhooks — refreshed from `thread.thread_assignment_transitioned` when the assignee is a machine user |

Handlers re-fetch entities via GraphQL before upserting (except customer delete, which uses the payload id).

## Limitations

- Live events are off by default. Enable with `enableLiveEvents` and a reachable `OCEAN__BASE_URL`.
- Plain does not emit dedicated company/tenant/user webhooks; those kinds update only when related thread/customer events fire.
- Only the UK GraphQL host is known to resolve. `apiUrl` is an override if Plain adds another region.
- Customer tenants come from the first page of `tenantMemberships` (at most 100). That selection needs `customerTenantMembership:read` in addition to `customer:read`.
- The user query selects `role`, which needs `roles:read` in addition to `user:read`.
- Thread messages come from `thread.timelineEntries`, which needs `timeline:read` in addition to `thread:read`.
- Thread tier is selected as nested `tier { id name }` and mapped to a string. That nested field may need `tier:read` in addition to `thread:read`.
- Discussions are loaded per thread with `discussions(filters: { threadIds })`. Messages are `discussion.messages`. The public schema does not name those permissions.
- AI/agent discussions use Cursor and agent-session channel types. Set `excludeAiDiscussions: true` on the discussion and discussion-message selectors to skip them during resync and live events.
- A missing Plain permission fails that kind and logs the permission name. The other kinds still sync.
- Company fields are `id`, `name`, and `domainName`. Company has no `externalId`.
- A thread assignee is a `User`, `MachineUser`, or `System`. Human assignees map to `assignee` (`plainUser`); machine assignees map to `machineAssignee` (`plainMachineUser`). `assigneeType` stores `__typename`.
- Machine-user list/get may need `machineUser:read` on the API key.
- HTTP failures (including a missing token) raise before GraphQL parsing. A GraphQL `errors` array fails the sync instead of yielding an empty page.
