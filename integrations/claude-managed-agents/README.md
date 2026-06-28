# Claude Managed Agents

An Ocean integration that imports [Claude Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) resources into Port, keeps them fresh via webhooks, and exposes actions to create and trigger agents from Port workflows.

## Capabilities

### Resources (resync)

The integration syncs the following kinds via the official Anthropic Python SDK (Managed Agents beta):

- `agent`
- `environment`
- `session`
- `vault`
- `memory-store`

### Live events (webhooks)

When a webhook signing secret is configured, the integration verifies and processes Anthropic webhooks:

- `session.*` events keep `session` entities up to date.
- `vault.*` and `vault_credential.*` events keep `vault` entities up to date.
- Session terminal events (`session.idled`, `session.status_idled`, `session.status_terminated`) report the status of `trigger_agent` runs back to Port. `session.error` events for the interaction are written to the run logs, scoped after the last `session.status_idle` before the anchor user message (`created_at_gt`) through webhook time; on a new session with no prior idle, no lower bound is applied. Run success or failure is derived only from the terminal idle `stop_reason` (for example `end_turn` is success, `retries_exhausted` is failure); `session.error` is informational and may be non-fatal. On success, the node run `output` includes `response` with the last agent message text for the interaction. On failure, `output` includes `error` with the last run log entry at ERROR level from that interaction (warnings are excluded).

Anthropic webhooks are configured in the Claude Console (there is no create-subscription API). Point the webhook at the integration's `/webhook` endpoint and copy the signing secret into the `webhookSigningSecret` configuration.

### Actions

Two actions are available for use from Port workflows:

- `create_agent` - creates a new managed agent and reflects it into the catalog. Completes synchronously.
- `trigger_agent` - starts a new session or continues an idle session for an agent, sends a user message, and (optionally) reports the run status back to Port when the session reaches a terminal state. When starting a new session you can pass optional session fields via `config` (for example `title`, `metadata`, `vault_ids`, `resources`). Each run is correlated via `externalRunId` `claude_session_{sessionId}_{userMessageEventId}`. Use the `sessionId` output from a previous run to send follow-up prompts in the same session.

## Configuration

| Name | Required | Description |
|------|----------|-------------|
| `anthropicApiKey` | yes | Anthropic API key used to authenticate with the Anthropic API. |
| `anthropicApiHost` | no | Anthropic API host. Defaults to `https://api.anthropic.com`. |
| `anthropicVersion` | no | Anthropic API version. Defaults to `2023-06-01`. |
| `webhookSigningSecret` | no | Signing secret from the Claude Console webhook configuration. Required to enable live events. |
| `githubAuthorizationToken` | no | Optional GitHub PAT injected into `github_repository` session resources when the workflow supplies URLs only. Stored in integration config as `github_authorization_token`. |

Set `OCEAN__PORT__BASE_MCP_URL` alongside `OCEAN__PORT__BASE_URL` for Port MCP vault auto-provisioning (for example `https://mcp.us.port.io/v1` for US). When omitted, the MCP URL is inferred from the Port API base URL region.

## Workflow usage

Add a `Create Claude Agent`, `Sync Claude Skill`, or `Trigger Claude Agent` node to a Port workflow. The nodes use the generic integration-action node with `integrationProvider: claude-managed-agents` and `integrationInvocationType` set to `create_agent`, `sync_skill`, or `trigger_agent`.

Workflow forms use [Port-native user input formats](https://docs.port.io/workflows/build-workflows/self-service-trigger/user-inputs/entity) (entity pickers, URL arrays, enums). The integration node assembles the Anthropic API `config` object via JQ. The action spec stays a thin `config` passthrough.

The `config` input is type `jqObject`: set it to a JSON **object** whose values are `{{ ... }}` JQ templates (same pattern as GitHub `workflowInputs`), not a single string expression.

### Trigger Claude Agent workflow

The workflow below supports starting a **new session** or **continuing an idle session**. Session fields are collected on the form and merged into `config` on the integration node.

```json
{
  "title": "Trigger Claude Agent",
  "icon": "Claude",
  "description": "Trigger a Claude managed agent by starting a new session or continuing an idle session with a follow-up prompt.",
  "category": "Claude Agents",
  "allowAnyoneToViewRuns": true,
  "nodes": [
    {
      "identifier": "trigger",
      "title": "Trigger Claude Agent",
      "icon": "Claude",
      "description": null,
      "config": {
        "type": "SELF_SERVE_TRIGGER",
        "contexts": [
          {
            "on": "ENTITY",
            "userInput": "sessionId"
          }
        ],
        "userInputs": {
          "properties": {
            "sessionMode": {
              "title": "Session mode",
              "description": "Start a new session, or continue an existing idle session with another prompt.",
              "type": "string",
              "enum": ["new", "continue"],
              "default": {
                "jqQuery": "if ((.form.sessionId // \"\") | length) > 0 then \"continue\" else \"new\" end"
              }
            },
            "agentId": {
              "title": "Agent",
              "description": "The Claude agent to run.",
              "type": "string",
              "format": "entity",
              "blueprint": "claude_agent"
            },
            "environmentId": {
              "title": "Environment",
              "description": "Required when starting a new session. Ignored when continuing an existing session.",
              "type": "string",
              "format": "entity",
              "blueprint": "claude_environment",
              "disabled": {
                "jqQuery": ".form.sessionMode != \"new\""
              }
            },
            "sessionId": {
              "title": "Session",
              "description": "Select an idle session to continue. Only shown when continuing a session.",
              "type": "string",
              "format": "entity",
              "blueprint": "claude_session",
              "dataset": {
                "combinator": "and",
                "rules": [
                  {
                    "property": "status",
                    "operator": "=",
                    "value": "idle"
                  }
                ]
              },
              "disabled": {
                "jqQuery": ".form.sessionMode != \"continue\""
              }
            },
            "title": {
              "title": "Session title",
              "description": "Optional title for a new session.",
              "type": "string",
              "disabled": {
                "jqQuery": ".form.sessionMode != \"new\""
              }
            },
            "metadata": {
              "title": "Metadata",
              "description": "Optional key-value metadata for a new session.",
              "type": "object",
              "disabled": {
                "jqQuery": ".form.sessionMode != \"new\""
              }
            },
            "vaultIds": {
              "title": "Vaults",
              "description": "Optional vaults to attach when starting a new session (for example a vault with Port MCP credentials).",
              "type": "array",
              "items": {
                "type": "string",
                "format": "entity",
                "blueprint": "claude_vault"
              },
              "disabled": {
                "jqQuery": ".form.sessionMode != \"new\""
              }
            },
            "memoryStoreIds": {
              "title": "Memory stores",
              "description": "Optional memory stores to attach to the session. The agent should have agent_toolset_20260401 enabled.",
              "type": "array",
              "items": {
                "type": "string",
                "format": "entity",
                "blueprint": "claude_memory_store"
              },
              "disabled": {
                "jqQuery": ".form.sessionMode != \"new\""
              }
            },
            "githubRepoUrls": {
              "title": "GitHub repositories",
              "description": "Optional GitHub repository URLs to mount. Requires github_authorization_token on the integration.",
              "type": "array",
              "items": {
                "type": "string",
                "format": "url"
              },
              "disabled": {
                "jqQuery": ".form.sessionMode != \"new\""
              }
            },
            "portMcpVaultStrategy": {
              "title": "Port MCP vault strategy",
              "description": "How to provision Port MCP vault credentials for this session.",
              "type": "string",
              "enum": ["manual", "attach_to_existing", "create_new"],
              "default": "manual"
            },
            "portMcpVaultId": {
              "title": "Port MCP vault",
              "description": "Vault to attach Port MCP credentials to. Required when strategy is attach_to_existing.",
              "type": "string",
              "format": "entity",
              "blueprint": "claude_vault",
              "disabled": {
                "jqQuery": ".form.portMcpVaultStrategy != \"attach_to_existing\""
              }
            },
            "prompt": {
              "title": "Prompt",
              "description": "The user message sent to the agent.",
              "type": "string",
              "format": "multi-line"
            }
          },
          "required": [
            "sessionMode",
            "agentId",
            "environmentId",
            "sessionId",
            "prompt"
          ],
          "order": [
            "sessionMode",
            "agentId",
            "environmentId",
            "sessionId",
            "title",
            "metadata",
            "vaultIds",
            "memoryStoreIds",
            "githubRepoUrls",
            "portMcpVaultStrategy",
            "portMcpVaultId",
            "prompt"
          ],
          "validations": [
            {
              "constraint": "if .form.sessionMode == \"new\" then ((.form.environmentId // \"\") | length) > 0 else true end",
              "message": "Select an environment when starting a new session."
            },
            {
              "constraint": "if .form.sessionMode == \"continue\" then ((.form.sessionId // \"\") | length) > 0 else true end",
              "message": "Select an idle session to continue."
            },
            {
              "constraint": "if .form.portMcpVaultStrategy == \"attach_to_existing\" then ((.form.portMcpVaultId // \"\") | length) > 0 else true end",
              "message": "Select a vault when using attach_to_existing Port MCP strategy."
            }
          ]
        },
        "actionCardButtonText": "Trigger",
        "executeActionButtonText": "Trigger",
        "published": true,
        "permissions": {
          "roles": ["Member", "Admin"]
        }
      },
      "variables": {},
      "links": [],
      "verbose": false
    },
    {
      "identifier": "trigger_agent",
      "title": "Trigger Claude Agent",
      "icon": "Claude",
      "description": null,
      "config": {
        "type": "INTEGRATION_ACTION",
        "installationId": "claude-managed-agents",
        "integrationProvider": "claude-managed-agents",
        "integrationInvocationType": "trigger_agent",
        "integrationActionExecutionProperties": {
          "prompt": "{{ .outputs.trigger.prompt }}",
          "agentId": "{{ .outputs.trigger.agentId }}",
          "environmentId": "{{ .outputs.trigger.environmentId }}",
          "sessionId": "{{ .outputs.trigger.sessionId }}",
          "config": {
            "title": "{{ .outputs.trigger.title }}",
            "metadata": "{{ .outputs.trigger.metadata }}",
            "vault_ids": "{{ .outputs.trigger.vaultIds }}",
            "resources": "{{ ([(.outputs.trigger.githubRepoUrls // [])[] | {type: \"github_repository\", url: .}] + [(.outputs.trigger.memoryStoreIds // [])[] | {type: \"memory_store\", memory_store_id: .}]) }}",
            "port_mcp_vault_strategy": "{{ .outputs.trigger.portMcpVaultStrategy }}",
            "port_mcp_vault_id": "{{ .outputs.trigger.portMcpVaultId }}"
          },
          "reportSessionStatus": true
        },
        "onFailure": "terminate"
      },
      "variables": {},
      "links": [],
      "verbose": false
    }
  ],
  "connections": [
    {
      "description": null,
      "sourceIdentifier": "trigger",
      "targetIdentifier": "trigger_agent"
    }
  ]
}
```

`port_mcp_vault_strategy` values (for new and continued sessions):

- `manual` - pass through `vaultIds` only; vault credentials must already exist.
- `attach_to_existing` - integration adds or updates a Port MCP `static_bearer` credential on `portMcpVaultId` using the integration's Port machine token and `OCEAN__PORT__BASE_MCP_URL`.
- `create_new` - integration creates a vault, adds the credential, and registers the vault entity in Port.

When `githubRepoUrls` are included in session `resources`, the integration updates the target agent to declare the [GitHub MCP server](https://platform.claude.com/docs/en/managed-agents/github) (`https://api.githubcopilot.com/mcp/`) and matching `mcp_toolset` if they are not already configured. It also stores a `static_bearer` vault credential for that MCP URL using `github_authorization_token` (on the same vault as Port MCP when auto-provisioned, or on the first configured `vaultIds` entry). Repository clone auth still comes from `authorization_token` on each `github_repository` resource (injected from `github_authorization_token` when omitted).

### Sync Port skill to Claude workflow

Upload a published Port `_skill` to Claude and register a `claude_skill` catalog entity. Run this before attaching skills to agents via the create-agent workflow.

Import the ready-made workflow from [`.port/examples/workflows/sync-port-skill-to-claude.json`](.port/examples/workflows/sync-port-skill-to-claude.json) via **Workflows → Create workflow → Import JSON**, or `POST /v1/workflows` with the file body. Replace `installationId` on the integration node if your Claude Managed Agents installation uses a different identifier.

```json
{
  "title": "Sync Port skill to Claude",
  "icon": "Claude",
  "description": "Upload a published Port skill to Claude and register a claude_skill entity.",
  "category": "Claude Agents",
  "allowAnyoneToViewRuns": true,
  "nodes": [
    {
      "identifier": "trigger",
      "title": "Sync Claude Skill",
      "icon": "Claude",
      "description": null,
      "config": {
        "type": "SELF_SERVE_TRIGGER",
        "userInputs": {
          "properties": {
            "portSkillId": {
              "title": "Port skill",
              "description": "Published Port skill to upload to Claude.",
              "type": "string",
              "format": "entity",
              "blueprint": "_skill",
              "dataset": {
                "combinator": "and",
                "rules": [
                  {
                    "property": "published_status",
                    "operator": "=",
                    "value": "published"
                  }
                ]
              }
            }
          },
          "required": ["portSkillId"],
          "order": ["portSkillId"]
        },
        "actionCardButtonText": "Sync",
        "executeActionButtonText": "Sync",
        "published": true,
        "permissions": {
          "roles": ["Member", "Admin"]
        }
      },
      "variables": {},
      "links": [],
      "verbose": false
    },
    {
      "identifier": "sync_skill",
      "title": "Sync Claude Skill",
      "icon": "Claude",
      "description": null,
      "config": {
        "type": "INTEGRATION_ACTION",
        "installationId": "claude-managed-agents",
        "integrationProvider": "claude-managed-agents",
        "integrationInvocationType": "sync_skill",
        "integrationActionExecutionProperties": {
          "portSkillId": "{{ .outputs.trigger.portSkillId }}"
        },
        "onFailure": "terminate"
      },
      "variables": {},
      "links": [],
      "verbose": false
    }
  ],
  "connections": [
    {
      "description": null,
      "sourceIdentifier": "trigger",
      "targetIdentifier": "sync_skill"
    }
  ]
}
```

### Create Claude Agent workflow

```json
{
  "title": "Create Claude Agent",
  "icon": "Claude",
  "description": "Create a new Claude managed agent with optional Port MCP and multi-agent coordinator settings.",
  "category": "Claude Agents",
  "allowAnyoneToViewRuns": true,
  "nodes": [
    {
      "identifier": "trigger",
      "title": "Create Claude Agent",
      "icon": "Claude",
      "description": null,
      "config": {
        "type": "SELF_SERVE_TRIGGER",
        "userInputs": {
          "properties": {
            "name": {
              "title": "Name",
              "description": "Human-readable name for the agent.",
              "type": "string"
            },
            "model": {
              "title": "Model",
              "description": "Claude model identifier.",
              "type": "string",
              "enum": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"]
            },
            "systemPrompt": {
              "title": "System prompt",
              "description": "System prompt defining agent behavior.",
              "type": "string",
              "format": "multi-line"
            },
            "description": {
              "title": "Description",
              "description": "Optional description of what the agent does.",
              "type": "string"
            },
            "enableAgentToolset": {
              "title": "Enable agent toolset",
              "description": "Enable agent_toolset_20260401 (required when sessions use memory stores).",
              "type": "boolean",
              "default": true
            },
            "enablePortMcp": {
              "title": "Enable Port MCP",
              "description": "Attach the Port MCP server and matching mcp_toolset to the agent.",
              "type": "boolean",
              "default": false
            },
            "multiagentMode": {
              "title": "Multi-agent mode",
              "description": "Coordinator agents can delegate work to a roster of other agents.",
              "type": "string",
              "enum": ["none", "coordinator"],
              "default": "none"
            },
            "delegateAgentIds": {
              "title": "Delegate agents",
              "description": "Agents the coordinator may spawn (max 20).",
              "type": "array",
              "maxItems": 20,
              "items": {
                "type": "string",
                "format": "entity",
                "blueprint": "claude_agent"
              },
              "disabled": {
                "jqQuery": ".form.multiagentMode != \"coordinator\""
              }
            },
            "allowSelfDelegation": {
              "title": "Allow self delegation",
              "description": "Allow the coordinator to invoke itself.",
              "type": "boolean",
              "default": false,
              "disabled": {
                "jqQuery": ".form.multiagentMode != \"coordinator\""
              }
            },
            "claudeSkillIds": {
              "title": "Claude skills",
              "description": "Synced Claude skills to attach to the agent (latest version is used).",
              "type": "array",
              "items": {
                "type": "string",
                "format": "entity",
                "blueprint": "claude_skill"
              }
            }
          },
          "required": ["name", "model", "systemPrompt"],
          "order": [
            "name",
            "model",
            "systemPrompt",
            "description",
            "enableAgentToolset",
            "enablePortMcp",
            "multiagentMode",
            "delegateAgentIds",
            "allowSelfDelegation",
            "claudeSkillIds"
          ],
          "validations": [
            {
              "constraint": "if .form.multiagentMode == \"coordinator\" then ((.form.delegateAgentIds // []) | length) > 0 or .form.allowSelfDelegation == true else true end",
              "message": "Select at least one delegate agent or enable self delegation."
            }
          ]
        },
        "actionCardButtonText": "Create",
        "executeActionButtonText": "Create",
        "published": true,
        "permissions": {
          "roles": ["Member", "Admin"]
        }
      },
      "variables": {},
      "links": [],
      "verbose": false
    },
    {
      "identifier": "create_agent",
      "title": "Create Claude Agent",
      "icon": "Claude",
      "description": null,
      "config": {
        "type": "INTEGRATION_ACTION",
        "installationId": "claude-managed-agents",
        "integrationProvider": "claude-managed-agents",
        "integrationInvocationType": "create_agent",
        "integrationActionExecutionProperties": {
          "name": "{{ .outputs.trigger.name }}",
          "model": "{{ .outputs.trigger.model }}",
          "systemPrompt": "{{ .outputs.trigger.systemPrompt }}",
          "config": {
            "description": "{{ .outputs.trigger.description }}",
            "{{ if .outputs.trigger.enablePortMcp then \"mcp_servers\" else null end }}": "{{ if .outputs.trigger.enablePortMcp then [{type: \"url\", name: \"port\"}] else null end }}",
            "{{ if (.outputs.trigger.enableAgentToolset or .outputs.trigger.enablePortMcp) then \"tools\" else null end }}": "{{ ((if .outputs.trigger.enableAgentToolset then [{type: \"agent_toolset_20260401\"}] else [] end) + (if .outputs.trigger.enablePortMcp then [{type: \"mcp_toolset\", mcp_server_name: \"port\"}] else [] end)) }}",
            "{{ if .outputs.trigger.multiagentMode == \"coordinator\" then \"multiagent\" else null end }}": "{{ if .outputs.trigger.multiagentMode == \"coordinator\" then {type: \"coordinator\", agents: ([(.outputs.trigger.delegateAgentIds // [])[]] + (if .outputs.trigger.allowSelfDelegation then [{type: \"self\"}] else [] end))} else null end }}",
            "{{ if ((.outputs.trigger.claudeSkillIds // []) | length) > 0 then \"skills\" else null end }}": "{{ [(.outputs.trigger.claudeSkillIds // [])[] | {type: \"custom\", skill_id: .}] }}"
          }
        },
        "onFailure": "terminate"
      },
      "variables": {},
      "links": [],
      "verbose": false
    }
  ],
  "connections": [
    {
      "description": null,
      "sourceIdentifier": "trigger",
      "targetIdentifier": "create_agent"
    }
  ]
}
```

When `enablePortMcp` is true, the integration sets the Port MCP server URL from `OCEAN__PORT__BASE_MCP_URL` (or infers EU/US from `OCEAN__PORT__BASE_URL`) when the agent is created, and sets the Port `mcp_toolset` permission policy to `always_allow` (Anthropic defaults MCP toolsets to `always_ask`). The workflow only declares the server name (`port`); vault credential `mcp_server_url` at session time uses the same URL resolution.

When starting a new session, pass optional session fields through `config`. The workflow form exposes friendly fields and merges them into `config` on the integration node.

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)
