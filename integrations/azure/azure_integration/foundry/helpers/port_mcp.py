from __future__ import annotations

import hashlib
from typing import Any, Literal

from loguru import logger
from port_ocean.context.ocean import ocean

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


def ootb_toolbox_name(agent_id: str) -> str:
    return _agent_resource("port-mcps", agent_id)


def toolbox_consumer_url(project_endpoint: str, toolbox_name: str) -> str:
    return f"{project_endpoint.rstrip('/')}/toolboxes/{toolbox_name}/mcp?api-version=v1"


def _bearer_value(token: str) -> str:
    token = token.strip()
    return token if token.lower().startswith("bearer ") else f"Bearer {token}"


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
    client: Any,
    *,
    project_endpoint: str,
    name: str,
    target: str,
    access_token: str,
) -> None:
    await client.send_api_request(
        client.build_url(project_endpoint, f"connections/{name}"),
        method="PUT",
        json_body={
            "name": name,
            "type": "CustomKeys",
            "target": target,
            "credentials": {
                "type": "CustomKeys",
                "Authorization": _bearer_value(access_token),
            },
        },
    )


async def upsert_ootb_toolbox(
    client: Any,
    *,
    project_endpoint: str,
    toolbox_name: str,
    tools: list[dict[str, Any]],
) -> None:
    await client.send_api_request(
        client.build_url(project_endpoint, f"toolboxes/{toolbox_name}/versions"),
        method="POST",
        json_body={
            "description": "Port Ocean ootb MCP toolbox (Port ± GitHub)",
            "tools": tools,
        },
        extra_headers=_TOOLBOXES_HEADER,
    )


async def _patch_agent_tools(
    client: Any,
    *,
    project_endpoint: str,
    agent_id: str,
    tools: list[Any],
) -> None:
    await client.send_api_request(
        client.build_url(project_endpoint, f"agents/{agent_id}"),
        method="PATCH",
        json_body={"definition": {"tools": tools}},
    )


async def ensure_ootb_mcp(
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
) -> str | None:
    toolbox_tools: list[dict[str, Any]] = []

    if enable_port_mcp:
        if not port_access_token:
            logger.warning(
                f"enablePortMcp set for agent {agent_id} but no execution "
                "identity token; skipping Port MCP connection"
            )
        else:
            conn = port_connection_name(agent_id)
            port_url = required_port_mcp_url()
            await upsert_custom_keys_connection(
                client,
                project_endpoint=project_endpoint,
                name=conn,
                target=port_url,
                access_token=port_access_token,
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
            client,
            project_endpoint=project_endpoint,
            name=conn,
            target=GITHUB_MCP_URL,
            access_token=git_access_token,
        )
        toolbox_tools.append(
            _mcp_toolbox_tool(
                server_label=GITHUB_MCP_SERVER_LABEL,
                server_url=GITHUB_MCP_URL,
                project_connection_id=conn,
            )
        )

    if include_existing_port_in_toolbox and not enable_port_mcp:
        conn = port_connection_name(agent_id)
        port_url = required_port_mcp_url()
        toolbox_tools.append(
            _mcp_toolbox_tool(
                server_label=PORT_MCP_SERVER_LABEL,
                server_url=port_url,
                project_connection_id=conn,
            )
        )

    if not toolbox_tools:
        if attach_to_prompt_agent and existing_tools is not None:
            stripped = merge_toolbox_into_tools(existing_tools, toolbox_url=None)
            if stripped != existing_tools:
                await _patch_agent_tools(
                    client,
                    project_endpoint=project_endpoint,
                    agent_id=agent_id,
                    tools=stripped,
                )
        return None

    toolbox_name = ootb_toolbox_name(agent_id)
    await upsert_ootb_toolbox(
        client,
        project_endpoint=project_endpoint,
        toolbox_name=toolbox_name,
        tools=toolbox_tools,
    )

    if not attach_to_prompt_agent:
        return toolbox_name

    toolbox_url = toolbox_consumer_url(project_endpoint, toolbox_name)
    tools = list(existing_tools) if existing_tools is not None else []
    if existing_tools is None:
        agent = await _load_agent(
            client, project_endpoint=project_endpoint, agent_id=agent_id
        )
        kind = (agent.get("definition") or {}).get("kind") or "prompt"
        if kind != "prompt":
            return toolbox_name
        tools = tools_from_agent_payload(agent)

    try:
        await _patch_agent_tools(
            client,
            project_endpoint=project_endpoint,
            agent_id=agent_id,
            tools=merge_toolbox_into_tools(tools, toolbox_url=toolbox_url),
        )
    except Exception as error:
        logger.warning(f"Failed to attach ootb toolbox on agent {agent_id}: {error}")
    return toolbox_name


def sanitize_git_provider(value: str | None) -> GitProvider:
    provider = (value or "github").strip().lower()
    if provider != "github":
        raise ValueError(f'Unsupported gitProvider "{value}" (only github)')
    return "github"
