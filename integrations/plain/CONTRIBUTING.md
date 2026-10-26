# Contributing to Ocean - plain

## Running locally

1. From `integrations/plain`, create a gitignored env file: `cp .env.example .env`
2. Fill in the Port client id and secret, and `OCEAN__INTEGRATION__CONFIG__API_TOKEN` with a Plain machine-user API key. Do not commit `.env`.
3. For live events, set `OCEAN__BASE_URL` to a reachable URL (for example an ngrok tunnel) and optionally `OCEAN__INTEGRATION__CONFIG__WEBHOOK_SECRET`. Registration runs when the event listener supports webhooks (for example `POLLING`).
4. Start the integration with `make run`, or `poetry run python debug.py`.

The API key needs the read permissions listed in the README kinds table (including nested ones such as `roles:read`, `timeline:read`, and discussion permissions). Requests go to `https://core-api.uk.plain.com/graphql/v1` unless `OCEAN__INTEGRATION__CONFIG__API_URL` is set. To verify credentials without a resync, run `poetry run python debug_probe.py` or `ocean probe`.
