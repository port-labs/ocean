from __future__ import annotations

import hashlib
from typing import Any, Literal

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from azure_integration.foundry.helpers.toolbox import (
    attach_toolbox_to_prompt_agent,
    ensure_toolbox_version,
    toolbox_name_from_agent_tools,
)
from azure_integration.foundry.models.agent import Agent, PromptAgentDefinition
from azure_integration.foundry.models.toolbox import (
    GITHUB_MCP_SERVER_LABEL,
    PORT_MCP_SERVER_LABEL,
    Tool,
)

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp"
GitProvider = Literal["github"]


def required_port_mcp_url() -> str:
    url = ocean.config.port.mcp_url
    if not url:
        raise RuntimeError("Port MCP URL is not configured for this integration")
    return str(url).rstrip("/")


def _slug(agent_id: str) -> str:
    return hashlib.sha1(agent_id.encode()).hexdigest()[:10]


def port_connection_name(agent_id: str) -> str:
    return f"port-mcp-{_slug(agent_id)}"


def github_connection_name(agent_id: str) -> str:
    return f"github-mcp-{_slug(agent_id)}"


def port_toolbox_name(agent_id: str) -> str:
    return f"port-mcps-{_slug(agent_id)}"


def agent_definition_kind(agent: dict[str, Any] | None) -> str:
    if not isinstance(agent, dict) or "versions" not in agent:
        return "prompt"
    return Agent.model_validate(agent).kind


def tools_from_agent_payload(agent: Any) -> list[Any]:
    if not isinstance(agent, dict) or "versions" not in agent:
        return []
    definition = Agent.model_validate(agent).latest_version.definition
    return (
        definition.tools if isinstance(definition, PromptAgentDefinition) else []
    )


async def upsert_custom_keys_connection(
    *,
    project_endpoint: str,
    name: str,
    target: str,
    access_token: str,
    project_arm_id: str | None = None,
) -> None:
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


def _mcp_tool(*, label: str, url: str, connection: str) -> Tool:
    return Tool(
        type="mcp",
        server_label=label,
        server_url=url,
        require_approval="never",
        project_connection_id=connection,
    )


def _resolve_target(
    *,
    agent_id: str,
    kind: str,
    existing_tb: str | None,
    toolbox_name: str | None,
    use_existing_toolbox: bool,
) -> tuple[str | None, bool, bool, str | None]:
    """(toolbox, create_if_missing, attach, skip_warning). None toolbox => skip MCP."""
    generated = port_toolbox_name(agent_id)
    if kind == "hosted":
        explicit = (toolbox_name or "").strip() or None
        if explicit:
            return explicit, False, False, None
        return generated, True, False, None
    if existing_tb is None or existing_tb == generated:
        # Always (re)attach so agent tools pin the current toolbox version URL.
        return generated, True, True, None
    if use_existing_toolbox:
        return existing_tb, True, False, None
    skip_warning = (
        f"Prompt agent {agent_id} already has toolbox '{existing_tb}'. "
        "Skipping Port/GitHub MCP (set useExistingToolbox=true to merge). "
        "Invoke continues without MCP remint."
    )
    logger.warning(skip_warning)
    return None, False, False, skip_warning


async def _collect_mcp_tools(
    *,
    agent_id: str,
    project_endpoint: str,
    project_arm_id: str | None,
    enable_port_mcp: bool,
    port_access_token: str | None,
    git_access_token: str | None,
) -> list[Tool]:
    tools: list[Tool] = []
    if enable_port_mcp and port_access_token:
        conn = port_connection_name(agent_id)
        url = required_port_mcp_url()
        await upsert_custom_keys_connection(
            project_endpoint=project_endpoint,
            name=conn,
            target=url,
            access_token=port_access_token,
            project_arm_id=project_arm_id,
        )
        tools.append(_mcp_tool(label=PORT_MCP_SERVER_LABEL, url=url, connection=conn))
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
        tools.append(
            _mcp_tool(label=GITHUB_MCP_SERVER_LABEL, url=GITHUB_MCP_URL, connection=conn)
        )
    return tools


async def ensure_port_mcp(
    client: Any,
    *,
    project_endpoint: str,
    agent_id: str,
    enable_port_mcp: bool,
    port_access_token: str | None,
    git_access_token: str | None = None,
    existing_tools: list[Any] | None = None,
    existing_agent: dict[str, Any] | None = None,
    toolbox_name: str | None = None,
    use_existing_toolbox: bool = False,
    agent_kind: str | None = None,
    project_arm_id: str | None = None,
    run: IntegrationRun | None = None,
) -> tuple[str, str] | None:
    agent = existing_agent or {}
    tools_context = (
        list(existing_tools)
        if existing_tools is not None
        else tools_from_agent_payload(agent)
    )
    kind = agent_kind or agent_definition_kind(agent)
    target, create_if_missing, should_attach, skip_warning = _resolve_target(
        agent_id=agent_id,
        kind=kind,
        existing_tb=toolbox_name_from_agent_tools(tools_context),
        toolbox_name=toolbox_name,
        use_existing_toolbox=use_existing_toolbox,
    )
    if target is None:
        if skip_warning and run is not None:
            await ocean.port_client.post_run_log(
                run, skip_warning, level="WARNING", should_raise=False
            )
        return None

    toolbox_tools = await _collect_mcp_tools(
        agent_id=agent_id,
        project_endpoint=project_endpoint,
        project_arm_id=project_arm_id,
        enable_port_mcp=enable_port_mcp,
        port_access_token=port_access_token,
        git_access_token=git_access_token,
    )
    if not toolbox_tools:
        return None

    version = await ensure_toolbox_version(
        client,
        project_endpoint=project_endpoint,
        toolbox_name=target,
        tools=toolbox_tools,
        create_if_missing=create_if_missing,
    )
    if should_attach and kind == "prompt":
        await attach_toolbox_to_prompt_agent(
            client,
            project_endpoint=project_endpoint,
            agent_id=agent_id,
            agent=agent,
            tools_context=tools_context,
            toolbox_name=target,
            version=version,
        )
    return target, version


def sanitize_git_provider(value: str | None) -> GitProvider:
    provider = (value or "github").strip().lower()
    if provider != "github":
        raise ValueError(f'Unsupported gitProvider "{value}" (only github)')
    return "github"
