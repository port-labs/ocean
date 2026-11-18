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
