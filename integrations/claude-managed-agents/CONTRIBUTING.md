# Contributing to Ocean - claude-managed-agents

## Running locally

```bash
cd integrations/claude-managed-agents
make install
cp .env.example .env
# fill in OCEAN__PORT__CLIENT_ID, OCEAN__PORT__CLIENT_SECRET, and
# OCEAN__INTEGRATION__CONFIG__ANTHROPIC_API_KEY
make run
```

## Gotchas

- Claude Managed Agents is a beta API and requires the `anthropic-beta: managed-agents-2026-04-01` header; the SDK sets it automatically for `client.beta.*` calls.
- Create endpoints (agents, sessions, environments) share a 300 requests/minute pool; read endpoints (list, retrieve) have a separate 1,200 requests/minute pool. Only the create-endpoints limit is proactively tracked, via `AnthropicClient.get_create_rate_limit_status`.
- Sending a user message only enqueues it on the session; the agent's response is asynchronous and surfaces later via the `session.status_idle` webhook.
