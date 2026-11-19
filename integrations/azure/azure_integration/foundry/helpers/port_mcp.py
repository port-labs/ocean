from __future__ import annotations

import hashlib
from typing import Any, Literal

from loguru import logger
from port_ocean.context.ocean import ocean

from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.core.exporters.agents_exporter import AgentsExporter
from azure_integration.foundry.core.options import SingleAgentOptions
from azure_integration.foundry.helpers.agent_api import (
    foundry_features_header,
    latest_agent_definition,
)
from azure_integration.foundry.helpers.utils import project_name_from_endpoint

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


def _slug(agent_id: str) -> str:
    return hashlib.sha1(agent_id.encode()).hexdigest()[:10]


def port_connection_name(agent_id: str) -> str:
    return f"port-mcp-{_slug(agent_id)}"


def github_connection_name(agent_id: str) -> str:
    return f"github-mcp-{_slug(agent_id)}"


def port_toolbox_name(agent_id: str) -> str:
    return f"port-mcps-{_slug(agent_id)}"


def resolve_toolbox_name(agent_id: str, toolbox_name: str | None = None) -> str:
    return (toolbox_name or "").strip() or port_toolbox_name(agent_id)


def agent_definition_kind(agent: dict[str, Any] | None) -> str:
    definition = agent.get("definition") if isinstance(agent, dict) else None
    kind = definition.get("kind") if isinstance(definition, dict) else None
    return kind if isinstance(kind, str) and kind else "prompt"


def toolbox_consumer_url(
    project_endpoint: str, toolbox_name: str, *, version: str | int
) -> str:
    return (
        f"{project_endpoint.rstrip('/')}/toolboxes/{toolbox_name}"
        f"/versions/{version}/mcp?api-version=v1"
    )


def _mcp_tool(label: str, url: str, connection_id: str) -> dict[str, Any]:
    return {
        "type": "mcp",
        "server_label": label,
        "server_url": url,
        "require_approval": "never",
        "project_connection_id": connection_id,
    }


def _managed_mcp(tool: Any) -> bool:
    return (
        isinstance(tool, dict)
        and tool.get("type") == "mcp"
        and tool.get("server_label") in (TOOLBOX_SERVER_LABEL, PORT_MCP_SERVER_LABEL)
    )


def _version_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("version", "version_id", "id", "name"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _tool_key(tool: dict[str, Any]) -> tuple[Any, ...]:
    return (
        tool.get("type"),
        tool.get("server_label"),
        tool.get("server_url"),
        tool.get("project_connection_id") or tool.get("projectConnectionId"),
    )


def _tools_satisfied(existing: list[Any] | None, desired: list[dict[str, Any]]) -> bool:
    if not desired:
        return True
    if not isinstance(existing, list):
        return False
    have = {_tool_key(t) for t in existing if isinstance(t, dict)}
    return all(_tool_key(t) in have for t in desired)


def _latest_toolbox(payload: Any) -> tuple[str, list[Any]] | None:
    if not isinstance(payload, dict):
        return None
    versions = payload.get("versions")
    latest = versions.get("latest") if isinstance(versions, dict) else None
    if not isinstance(latest, dict):
        return None
    version = _version_id(latest) or _version_id(
        {"version": payload.get("default_version")}
    )
    if not version:
        return None
    tools = latest.get("tools")
    return version, tools if isinstance(tools, list) else []


def _points_at_toolbox(tools: list[Any] | None, *, toolbox_name: str) -> bool:
    marker = f"/toolboxes/{toolbox_name}/"
    for tool in tools or []:
        if (
            isinstance(tool, dict)
            and tool.get("type") == "mcp"
            and tool.get("server_label") == TOOLBOX_SERVER_LABEL
            and isinstance(tool.get("server_url"), str)
            and marker in tool["server_url"]
        ):
            return True
    return False


def tools_from_agent_payload(agent: Any) -> list[Any]:
    definition = agent.get("definition") if isinstance(agent, dict) else None
    tools = definition.get("tools") if isinstance(definition, dict) else None
    return tools if isinstance(tools, list) else []


def merge_toolbox_into_tools(tools: list[Any], *, toolbox_url: str | None) -> list[Any]:
    others = [t for t in tools if not _managed_mcp(t)]
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


async def ensure_toolbox_version(
    client: Any,
    *,
    project_endpoint: str,
    toolbox_name: str,
    tools: list[dict[str, Any]],
) -> str:
    # ponytail: GET then subset-match; POST only when tools missing
    try:
        existing = await client.send_api_request(
            client.build_url(project_endpoint, f"toolboxes/{toolbox_name}"),
            extra_headers=_TOOLBOXES_HEADER,
        )
    except FoundryApiError as error:
        if error.status_code != 404:
            raise
        existing = None
    latest = _latest_toolbox(existing)
    if latest is not None:
        version, existing_tools = latest
        if _tools_satisfied(existing_tools, tools):
            return version
    response = await client.send_api_request(
        client.build_url(project_endpoint, f"toolboxes/{toolbox_name}/versions"),
        method="POST",
        json_body={
            "description": "Port toolbox (Port ± GitHub MCP)",
            "tools": tools,
        },
        extra_headers=_TOOLBOXES_HEADER,
    )
    return _version_id(response) or "1"


async def _update_agent_tools(
    client: Any,
    *,
    project_endpoint: str,
    agent_id: str,
    tools: list[Any],
    agent: dict[str, Any],
) -> None:
    # Foundry updates definitions via POST (new version). PATCH is endpoint-only.
    definition = {
        **(latest_agent_definition(agent) or {"kind": "prompt"}),
        "tools": tools,
    }
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
    toolbox_name: str | None = None,
    agent_kind: str | None = None,
    project_arm_id: str | None = None,
) -> tuple[str, str] | None:
    _ = git_provider
    toolbox_tools: list[dict[str, Any]] = []

    if enable_port_mcp and port_access_token:
        conn = port_connection_name(agent_id)
        port_url = required_port_mcp_url()
        await upsert_custom_keys_connection(
            project_endpoint=project_endpoint,
            name=conn,
            target=port_url,
            access_token=port_access_token,
            project_arm_id=project_arm_id,
        )
        toolbox_tools.append(_mcp_tool(PORT_MCP_SERVER_LABEL, port_url, conn))
    elif enable_port_mcp:
        logger.warning(
            f"enablePortMcp set for agent {agent_id} but no execution "
            "identity token; skipping Port MCP connection remint"
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
        toolbox_tools.append(_mcp_tool(GITHUB_MCP_SERVER_LABEL, GITHUB_MCP_URL, conn))

    agent_payload: dict[str, Any] = {}
    if existing_tools is not None:
        tools_context = list(existing_tools)
    else:
        try:
            loaded = await AgentsExporter(client).get_resource(
                SingleAgentOptions(
                    project_endpoint=project_endpoint,
                    project_id=project_arm_id
                    or project_name_from_endpoint(project_endpoint),
                    agent_id=agent_id,
                )
            )
            agent_payload = loaded or {}
        except Exception as error:
            logger.warning(f"Could not load agent {agent_id}: {error}")
        tools_context = tools_from_agent_payload(agent_payload)

    # Remint git without Port token: keep Port entry if agent already had toolbox.
    if (
        toolbox_tools
        and enable_port_mcp
        and not port_access_token
        and any(_managed_mcp(t) for t in tools_context)
        and not any(
            t.get("server_label") == PORT_MCP_SERVER_LABEL for t in toolbox_tools
        )
    ):
        toolbox_tools.append(
            _mcp_tool(
                PORT_MCP_SERVER_LABEL,
                required_port_mcp_url(),
                port_connection_name(agent_id),
            )
        )

    if not toolbox_tools:
        return None

    resolved = resolve_toolbox_name(agent_id, toolbox_name)
    version = await ensure_toolbox_version(
        client,
        project_endpoint=project_endpoint,
        toolbox_name=resolved,
        tools=toolbox_tools,
    )

    kind = agent_kind or agent_definition_kind(agent_payload)
    if not attach_to_prompt_agent or kind != "prompt":
        return resolved, version
    if _points_at_toolbox(tools_context, toolbox_name=resolved):
        return resolved, version

    await _update_agent_tools(
        client,
        project_endpoint=project_endpoint,
        agent_id=agent_id,
        tools=merge_toolbox_into_tools(
            tools_context,
            toolbox_url=toolbox_consumer_url(
                project_endpoint, resolved, version=version
            ),
        ),
        agent=agent_payload,
    )
    return resolved, version


def sanitize_git_provider(value: str | None) -> GitProvider:
    provider = (value or "github").strip().lower()
    if provider != "github":
        raise ValueError(f'Unsupported gitProvider "{value}" (only github)')
    return "github"
