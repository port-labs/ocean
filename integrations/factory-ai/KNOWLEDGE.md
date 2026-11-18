# Factory.ai integration knowledge

## Docs

- [Factory Public API](https://docs.factory.com/api-reference)
- [OpenAPI specification](https://factory.com/openapi.json)
- [API keys settings](https://app.factory.ai/settings/api-keys)

## Base URL

Production Public API host: `https://api.factory.ai`

Operation paths are relative to that host (for example `GET /api/v0/sessions`).

## Auth

Every Public API request uses a bearer token in the `Authorization` header:

```http
Authorization: Bearer <FACTORY_API_KEY>
```

Create keys in the Factory App (API keys settings). Keys are shown once; documented form is `fk-…`. Missing or invalid keys receive `401`.

## Live events

Factory has no outbound webhooks / push event API for the Public API surface we integrate against. Catalog freshness is resync-only; `saas.liveEvents.enabled` stays `false` and there is no webhook processor package.
