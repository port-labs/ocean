# Contributing to Ocean - plain

## Running locally

1. From `integrations/plain`, create a gitignored env file: `cp .env.example .env`
2. Fill in the Port client id and secret, and `OCEAN__INTEGRATION__CONFIG__API_TOKEN` with a Plain machine-user API key. Do not commit `.env`.
3. Leave `OCEAN__INTEGRATION__CONFIG__ENABLE_LIVE_EVENTS=false`. Webhook registration is not implemented.
4. Start the integration with `make run`, or `poetry run python debug.py`.

The API key needs `company:read`, `tenant:read`, `user:read`, `customer:read`, `thread:read`, and `timeline:read` (thread messages). Requests go to `https://core-api.uk.plain.com/graphql/v1` unless `OCEAN__INTEGRATION__CONFIG__API_URL` is set.
