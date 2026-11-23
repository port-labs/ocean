# Contributing to Ocean - factory-ai

## Running locally

```bash
cd integrations/factory-ai
make install
cp .env.example .env
# fill in OCEAN__PORT__CLIENT_ID, OCEAN__PORT__CLIENT_SECRET,
# and OCEAN__INTEGRATION__CONFIG__FACTORY_API_KEY
make run
```

## Gotchas

- Keep integration logic under the `factory_ai/` package. Root stays thin (`main.py`, `integration.py`, `debug_resync.py`) so flat imports like `clients` do not collide in a shared local dev env.
- Factory Public API auth is `Authorization: Bearer <api_key>` against `https://api.factory.ai` ([docs](https://docs.factory.com/api-reference)).
- Factory has no outbound webhooks, so `saas.liveEvents.enabled` stays `false` and there is no webhook processor package.
- Prefer Ocean's `http_async_client` over third-party SDKs for new client code.
