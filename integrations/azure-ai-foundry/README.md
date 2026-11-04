# Azure AI Foundry

Sync Microsoft Foundry agents, model deployments, and sessions into Port using **incremental resync** (no live-event polling).

## Local setup

```bash
cd integrations/azure-ai-foundry
make install
cp .env.example .env
# configure OCEAN__* and FOUNDRY_PROJECT_ENDPOINT
make run
```

## Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `foundryProjectEndpoint` | yes | Single project data-plane URL |
| `apiVersion` | no | REST `api-version` (default `v1`) |
| Azure SP fields | no | Use `DefaultAzureCredential` when omitted |

Catalog freshness relies on Port **incremental sync** schedules. **`invoke_agent`** completes workflow runs from **Responses SSE** (terminal events). Response webhooks are registered but not used for completion.

On startup (with `OCEAN__BASE_URL` set), the integration registers `{base}/integration/webhook` with Foundry. Agent / deployment CRUD webhooks are not exposed by Foundry today.

## Actions

- `create_agent`, `update_agent`, `delete_agent`
- `invoke_agent` — Responses SSE streamed to workflow run logs; optional Port MCP remint
- `invoke_model` — deployment-level Responses invoke
