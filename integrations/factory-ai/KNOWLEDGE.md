# Factory.ai integration knowledge

## Docs

- [Factory Public API](https://docs.factory.com/api-reference)
- [OpenAPI specification](https://factory.com/openapi.json)
- [API keys settings](https://app.factory.ai/settings/api-keys)

## Integration-wide

- Base URL: `https://api.factory.ai` (paths like `/api/v0/...`)
- Auth: `Authorization: Bearer <FACTORY_API_KEY>` (`fk-…`; `401` if missing/invalid)
- No outbound webhooks → resync-only; `saas.liveEvents.enabled` stays `false`
- Errors use a shared `FactoryApiError` envelope (`detail`, `status`, `title`, optional `metadata`)

## Kind notes

### environment

- List is **not paginated** (full `{ environments: [...] }` in one response; computers look the same)

### computer

- List is **not paginated** (`{ computers: [...] }`); newest first
- Relation to environment when `computerSource.kind` is `environment` (`environmentId`) or legacy `template` (`templateId`)

### user

- List is **cursor-paginated** (`{ users: [...], pagination: { hasMore, nextCursor } }`) via `/api/v0/organization/users`
- Page size: `limit` 1–100 (integration defaults to 100)
- No get-by-id endpoint; `get_resource` scans list pages
- List contract documents id/email/createdAt/metadata (+ optional names/lastSignInAt); role/status appear on invite responses and are retained when present

### session

- Selected-orgs feature (`403` when the org lacks Sessions API access)
- List is **cursor-paginated** (`{ sessions: [...], pagination: { hasMore, nextCursor } }`) via `/api/v0/sessions`
- Page size: `limit` 1–100 (integration defaults to 100); optional `computerId` filter
- Get-by-id: `GET /api/v0/sessions/{sessionId}` (optional `computerId` query)
- Identifier field is `sessionId` (not `id`); `parent_session_id` is snake_case in the OpenAPI contract
- Relations available on the payload: `computerId` → computer, `parent_session_id` → parent session
- No actor / environment fields on list or get — environment is only reachable via the related computer
