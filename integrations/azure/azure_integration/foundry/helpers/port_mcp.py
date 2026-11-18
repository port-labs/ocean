from __future__ import annotations

import hashlib
from typing import Any, Literal

from loguru import logger
from port_ocean.context.ocean import ocean

from azure_integration.foundry.helpers.agent_api import (
    foundry_features_header,
    latest_agent_definition,
)
from azure_integration.foundry.helpers.utils import deep_merge

PORT_MCP_SERVER_LABEL = "port"
GITHUB_MCP_SERVER_LABEL = "github"
TOOLBOX_SERVER_LABEL = "port-mcps"
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp"
_TOOLBOXES_HEADER = {"Foundry-Features": "Toolboxes=V1Preview"}
GitProvider = Literal["github"]


def required_port_mcp_url() -> str:
    port_mcp_url = ocean.config.port.mcp_url
    if not port_mcp_url:
        raise RuntimeError("Port MCP URL is not configured for this integration")
    return str(port_mcp_url).rstrip("/")


def _resource_slug(agent_id: str) -> str:
    return hashlib.sha1(agent_id.encode()).hexdigest()[:10]


def _agent_resource(prefix: str, agent_id: str) -> str:
    return f"{prefix}-{_resource_slug(agent_id)}"


def port_connection_name(agent_id: str) -> str:
    return _agent_resource("port-mcp", agent_id)


def github_connection_name(agent_id: str) -> str:
    return _agent_resource("github-mcp", agent_id)


def port_toolbox_name(agent_id: str) -> str:
    return _agent_resource("port-mcps", agent_id)


def resolve_toolbox_name(agent_id: str, toolbox_name: str | None = None) -> str:
    custom = (toolbox_name or "").strip()
    return custom or port_toolbox_name(agent_id)


def agent_definition_kind(agent: dict[str, Any] | None) -> str:
    if not isinstance(agent, dict):
        return "prompt"
    definition = agent.get("definition")
    if not isinstance(definition, dict):
        return "prompt"
    kind = definition.get("kind")
    return kind if isinstance(kind, str) and kind else "prompt"


def toolbox_consumer_url(
    project_endpoint: str, toolbox_name: str, *, version: str | int
) -> str:
    base = project_endpoint.rstrip("/")
    return (
        f"{base}/toolboxes/{toolbox_name}/versions/{version}/mcp?api-version=v1"
    )


def _mcp_toolbox_tool(
    *,
    server_label: str,
    server_url: str,
    project_connection_id: str,
) -> dict[str, Any]:
    return {
        "type": "mcp",
        "server_label": server_label,
        "server_url": server_url,
        "require_approval": "never",
        "project_connection_id": project_connection_id,
    }


def _managed_mcp_tool(tool: Any) -> bool:
    if not isinstance(tool, dict) or tool.get("type") != "mcp":
        return False
    label = tool.get("server_label")
    return label in (TOOLBOX_SERVER_LABEL, PORT_MCP_SERVER_LABEL)


def _agent_had_port_toolbox(tools: list[Any] | None) -> bool:
    if not tools:
        return False
    return any(_managed_mcp_tool(tool) for tool in tools)


def _port_toolbox_entry(agent_id: str) -> dict[str, Any]:
    conn = port_connection_name(agent_id)
    port_url = required_port_mcp_url()
    return _mcp_toolbox_tool(
        server_label=PORT_MCP_SERVER_LABEL,
        server_url=port_url,
        project_connection_id=conn,
    )


def _port_in_toolbox_entries(toolbox_tools: list[dict[str, Any]]) -> bool:
    return any(
        t.get("server_label") == PORT_MCP_SERVER_LABEL for t in toolbox_tools
    )


def _toolbox_version_from_response(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "1"
    for key in ("version", "id", "name", "version_id"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return "1"


def tools_from_agent_payload(agent: Any) -> list[Any]:
    if not isinstance(agent, dict):
        return []
    definition = agent.get("definition")
    if not isinstance(definition, dict):
        return []
    tools = definition.get("tools")
    return tools if isinstance(tools, list) else []


def merge_toolbox_into_tools(
    tools: list[Any],
    *,
    toolbox_url: str | None,
) -> list[Any]:
    others = [tool for tool in tools if not _managed_mcp_tool(tool)]
    if not toolbox_url:
        return others
    return [
        *others,
        {
            "type": "mcp",
            "server_label": TOOLBOX_SERVER_LABEL,
            "server_url": toolbox_url,
            "require_approval": "never",
        },
    ]


def attach_toolbox_to_agent_config(
    config: dict[str, Any],
    *,
    toolbox_url: str | None,
    existing_tools: list[Any] | None = None,
) -> dict[str, Any]:
    merged = deep_merge(
        {"definition": {"tools": list(existing_tools or [])}},
        config,
    )
    definition = merged.get("definition")
    if not isinstance(definition, dict):
        definition = {}
        merged["definition"] = definition
    tools = definition.get("tools")
    if not isinstance(tools, list):
        tools = []
    definition["tools"] = merge_toolbox_into_tools(tools, toolbox_url=toolbox_url)
    return merged


async def _load_agent(
    client: Any, *, project_endpoint: str, agent_id: str
) -> dict[str, Any]:
    try:
        agent = await client.send_api_request(
            client.build_url(project_endpoint, f"agents/{agent_id}")
        )
    except Exception as error:
        logger.warning(f"Could not load agent {agent_id}: {error}")
        return {}
    return agent if isinstance(agent, dict) else {}


async def fetch_agent_tools(
    client: Any, *, project_endpoint: str, agent_id: str
) -> list[Any]:
    return tools_from_agent_payload(
        await _load_agent(client, project_endpoint=project_endpoint, agent_id=agent_id)
    )


async def upsert_custom_keys_connection(
    *,
    project_endpoint: str,
    name: str,
    target: str,
    access_token: str,
    project_arm_id: str | None = None,
) -> None:
    # Data-plane /connections is GET-only; remint must go through ARM.
    from azure_integration.foundry.clients.client_factory import (
        create_foundry_arm_client,
    )

    await create_foundry_arm_client().upsert_project_connection(
        project_endpoint=project_endpoint,
        name=name,
        target=target,
        access_token=access_token,
        project_arm_id=project_arm_id,
    )


async def upsert_port_toolbox(
    client: Any,
    *,
    project_endpoint: str,
    toolbox_name: str,
    tools: list[dict[str, Any]],
) -> str:
    response = await client.send_api_request(
        client.build_url(project_endpoint, f"toolboxes/{toolbox_name}/versions"),
        method="POST",
        json_body={
            "description": "Port toolbox (Port ± GitHub MCP)",
            "tools": tools,
        },
        extra_headers=_TOOLBOXES_HEADER,
    )
    return _toolbox_version_from_response(response)


async def _update_agent_tools(
    client: Any,
    *,
    project_endpoint: str,
    agent_id: str,
    tools: list[Any],
    agent: dict[str, Any] | None = None,
) -> None:
    # Foundry updates agent definitions via POST (new version). PATCH is only
    # for endpoint config (version_selector / protocols) — 405 if misused here.
    existing = (
        agent
        if isinstance(agent, dict) and agent
        else await _load_agent(
            client, project_endpoint=project_endpoint, agent_id=agent_id
        )
    )
    definition = latest_agent_definition(existing) or {"kind": "prompt"}
    definition = {**definition, "tools": tools}
    kind = definition.get("kind") or "prompt"
    definition["kind"] = kind
    await client.send_api_request(
        client.build_url(project_endpoint, f"agents/{agent_id}"),
        method="POST",
        json_body={"definition": definition},
        extra_headers=foundry_features_header(kind),
    )


async def ensure_port_mcp(
    client: Any,
    *,
    project_endpoint: str,
    agent_id: str,
    enable_port_mcp: bool,
    port_access_token: str | None,
    git_access_token: str | None = None,
    git_provider: GitProvider = "github",
    attach_to_prompt_agent: bool = True,
    existing_tools: list[Any] | None = None,
    include_existing_port_in_toolbox: bool = False,
    toolbox_name: str | None = None,
    agent_kind: str | None = None,
    project_arm_id: str | None = None,
) -> tuple[str, str] | None:
    _ = git_provider
    toolbox_tools: list[dict[str, Any]] = []

    if enable_port_mcp:
        if not port_access_token:
            logger.warning(
                f"enablePortMcp set for agent {agent_id} but no execution "
                "identity token; skipping Port MCP connection remint"
            )
        else:
            conn = port_connection_name(agent_id)
            port_url = required_port_mcp_url()
            await upsert_custom_keys_connection(
                project_endpoint=project_endpoint,
                name=conn,
                target=port_url,
                access_token=port_access_token,
                project_arm_id=project_arm_id,
            )
            toolbox_tools.append(
                _mcp_toolbox_tool(
                    server_label=PORT_MCP_SERVER_LABEL,
                    server_url=port_url,
                    project_connection_id=conn,
                )
            )

    if git_access_token:
        conn = github_connection_name(agent_id)
        await upsert_custom_keys_connection(
            project_endpoint=project_endpoint,
            name=conn,
            target=GITHUB_MCP_URL,
            access_token=git_access_token,
            project_arm_id=project_arm_id,
        )
        toolbox_tools.append(
            _mcp_toolbox_tool(
                server_label=GITHUB_MCP_SERVER_LABEL,
                server_url=GITHUB_MCP_URL,
                project_connection_id=conn,
            )
        )

    agent_payload: dict[str, Any] | None = None
    if existing_tools is not None:
        tools_context = list(existing_tools)
    else:
        agent_payload = await _load_agent(
            client, project_endpoint=project_endpoint, agent_id=agent_id
        )
        tools_context = tools_from_agent_payload(agent_payload)
    should_preserve_port = (
        include_existing_port_in_toolbox or (enable_port_mcp and not port_access_token)
    ) and toolbox_tools and _agent_had_port_toolbox(tools_context)

    if should_preserve_port and not _port_in_toolbox_entries(toolbox_tools):
        toolbox_tools.append(_port_toolbox_entry(agent_id))

    if not toolbox_tools:
        # Nothing to remint (e.g. enablePortMcp without a token). Leave agent tools alone.
        return None

    resolved_toolbox_name = resolve_toolbox_name(agent_id, toolbox_name)
    toolbox_version = await upsert_port_toolbox(
        client,
        project_endpoint=project_endpoint,
        toolbox_name=resolved_toolbox_name,
        tools=toolbox_tools,
    )

    if not attach_to_prompt_agent:
        return resolved_toolbox_name, toolbox_version

    kind = agent_kind or agent_definition_kind(agent_payload)
    if kind != "prompt":
        return resolved_toolbox_name, toolbox_version

    toolbox_url = toolbox_consumer_url(
        project_endpoint, resolved_toolbox_name, version=toolbox_version
    )
    tools = list(tools_context)

    await _update_agent_tools(
        client,
        project_endpoint=project_endpoint,
        agent_id=agent_id,
        tools=merge_toolbox_into_tools(tools, toolbox_url=toolbox_url),
        agent=agent_payload,
    )
    return resolved_toolbox_name, toolbox_version


def sanitize_git_provider(value: str | None) -> GitProvider:
    provider = (value or "github").strip().lower()
    if provider != "github":
        raise ValueError(f'Unsupported gitProvider "{value}" (only github)')
    return "github"
