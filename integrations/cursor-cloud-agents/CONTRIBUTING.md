# Contributing to Ocean - cursor-cloud-agents

## Running locally

```bash
cd integrations/cursor-cloud-agents
make install
cp .env.example .env
# fill in OCEAN__PORT__CLIENT_ID, OCEAN__PORT__CLIENT_SECRET,
# OCEAN__INTEGRATION__CONFIG__CURSOR_API_KEY, and
# OCEAN__INTEGRATION__CONFIG__WEBHOOK_SIGNING_SECRET (required for v0 reportCompletion)
make run
```

## Gotchas

- Cursor's create endpoints (`POST /v0/agents`, `POST /v1/agents`) always require a `prompt` and immediately launch a run - there is no config-only create. `create_agent` therefore launches the first run and starts billing immediately.
- `apiVersion` on `create_agent` selects the Cursor create endpoint (`v0` or `v1`, default `v1`). `reportCompletion` only applies on **v0 create** - it attaches a webhook and leaves the Port run `IN_PROGRESS` until Cursor calls back (`FINISHED`/`ERROR`). On **v1 create**, `reportCompletion` is rejected (v1 has no webhooks) and the Port run always completes immediately after launch.
- `trigger_agent` always calls `POST /v1/agents/{id}/runs`. `reportCompletion` on trigger only keeps the Port run `IN_PROGRESS` when the agent already has a webhook registered (v0 create with `reportCompletion: true` and `OCEAN__BASE_URL`).
- Optionally configure `webhookSigningSecret` to sign outgoing v0 webhooks and verify incoming callbacks. When unset, signature verification is skipped. When set, the integration derives a per-run signing secret from `webhookSigningSecret`, the Port organization id, and the Port run id embedded in the per-run callback URL path (`/webhook/{run_id}`) - see `core/webhook_signing.py`.
- Webhook payloads carry no run-specific id. The processor resolves the completing Cursor run from the first page of List Runs at or before the webhook timestamp, then finds the in-progress Port run by Cursor run id (`trigger_agent`) or agent id (`create_agent`) via `externalRunId`.
- Cursor's Cloud Agents API rate limits aren't exposed via response headers. Backoff on `429`/`5xx` is handled by Ocean's retryable HTTP extension.
