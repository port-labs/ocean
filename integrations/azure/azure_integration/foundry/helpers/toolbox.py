from __future__ import annotations

from typing import Any

from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.models.agent import features_header_for_kind
from azure_integration.foundry.models.toolbox import (
    TOOLBOX_SERVER_LABEL,
    Tool,
    ToolboxLatest,
    parse_toolbox_latest,
)

_TOOLBOXES_HEADER = {"Foundry-Features": "Toolboxes=V1Preview"}


def _tools(raw: list[Any]) -> list[Tool]:
    return [Tool.model_validate(t) for t in raw if isinstance(t, dict)]


def toolbox_name_from_agent_tools(tools: list[Any]) -> str | None:
    for tool in _tools(tools):
        if tool.toolbox_name:
            return tool.toolbox_name
    return None


def merge_toolbox_into_tools(tools: list[Any], *, toolbox_url: str | None) -> list[Any]:
    others = [t.model_dump() for t in _tools(tools) if not t.is_managed]
    if not toolbox_url:
        return others
    return [
        *others,
        Tool(
            type="mcp",
            server_label=TOOLBOX_SERVER_LABEL,
            server_url=toolbox_url,
            require_approval="never",
        ).model_dump(),
    ]


async def ensure_toolbox_version(
    client: Any,
    *,
    project_endpoint: str,
    toolbox_name: str,
    tools: list[Tool],
    create_if_missing: bool = True,
) -> str:
    try:
        existing = await client.send_api_request(
            client.build_url(project_endpoint, f"toolboxes/{toolbox_name}"),
            extra_headers=_TOOLBOXES_HEADER,
        )
    except FoundryApiError as error:
        if error.status_code != 404:
            raise
        existing = None

    if existing is None and not create_if_missing:
        raise ValueError(f"Toolbox '{toolbox_name}' was not found")

    latest = parse_toolbox_latest(existing) if existing is not None else None
    if latest is not None and latest.contains_all(tools):
        return latest.version
    body_tools = (
        latest.merge(tools) if latest is not None else [t.model_dump() for t in tools]
    )
    response = await client.send_api_request(
        client.build_url(project_endpoint, f"toolboxes/{toolbox_name}/versions"),
        method="POST",
        json_body={
            "description": "Port toolbox (Port ± GitHub MCP)",
            "tools": body_tools,
        },
        extra_headers=_TOOLBOXES_HEADER,
    )
    return ToolboxLatest.model_validate(response).version


async def attach_toolbox_to_prompt_agent(
    client: Any,
    *,
    project_endpoint: str,
    agent_id: str,
    agent: dict[str, Any],
    tools_context: list[Any],
    toolbox_name: str,
    version: str,
) -> None:
    # Skip only when already pinned to this version (not an older one).
    version_path = f"/toolboxes/{toolbox_name}/versions/{version}/"
    if any(
        t.server_url and version_path in t.server_url for t in _tools(tools_context)
    ):
        return
    url = (
        f"{project_endpoint.rstrip('/')}/toolboxes/{toolbox_name}"
        f"/versions/{version}/mcp?api-version=v1"
    )
    await client.send_api_request(
        client.build_url(project_endpoint, f"agents/{agent_id}"),
        method="POST",
        json_body={
            "definition": {
                # Keep latest definition as-is; only rewrite tools to attach the toolbox.
                **agent["versions"]["latest"]["definition"],
                "tools": merge_toolbox_into_tools(tools_context, toolbox_url=url),
            }
        },
        extra_headers=features_header_for_kind("prompt"),
    )
