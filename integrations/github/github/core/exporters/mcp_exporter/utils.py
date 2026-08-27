from __future__ import annotations

from typing import Any, Iterator, Optional

from pydantic import BaseModel, Field

DEFAULT_MCP_PATHS: list[str] = [
    "mcp.json",
    ".mcp.json",
]


class McpServer(BaseModel):
    """Normalized MCP server entry parsed out of a single mcp.json/.mcp.json file."""

    name: str
    transport: str
    url: Optional[str] = None
    command: Optional[str] = None
    args: list[str] = Field(default_factory=list)
    headers: dict[str, Any] = Field(default_factory=dict)
    env: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    path: str
    blob_sha: Optional[str] = None


class McpRawItem(BaseModel):
    """Raw item emitted for the `mcp` kind, by both resync and webhooks."""

    mcp: McpServer
    repository: dict[str, Any] = Field(serialization_alias="__repository")
    branch: str = Field(serialization_alias="__branch")
    organization: Optional[str] = Field(
        default=None, serialization_alias="__organization"
    )


def iter_mcp_servers(content: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (name, server_config) pairs from a parsed mcp.json/.mcp.json document."""
    if not isinstance(content, dict):
        return
    mcp_servers = content.get("mcpServers")
    if not isinstance(mcp_servers, dict):
        return
    for name, server_config in mcp_servers.items():
        if isinstance(server_config, dict):
            yield name, server_config


def _build_mcp_server(
    *,
    file_path: str,
    server_name: str,
    server_config: dict[str, Any],
    blob_sha: Optional[str] = None,
) -> McpServer:
    url = server_config.get("url")
    return McpServer(
        name=server_name,
        transport="http" if url else "stdio",
        url=url,
        command=server_config.get("command"),
        args=server_config.get("args") or [],
        headers=server_config.get("headers") or {},
        env=server_config.get("env") or {},
        config=server_config,
        path=file_path,
        blob_sha=blob_sha,
    )


def build_mcp_raw_item(
    *,
    file_path: str,
    server_name: str,
    server_config: dict[str, Any],
    repository: dict[str, Any],
    branch: str,
    organization: Optional[str] = None,
    blob_sha: Optional[str] = None,
) -> dict[str, Any]:
    """Single entry point for building an mcp raw item.

    Webhook deletes call this with an empty ``server_config`` so that deleted
    entities carry the exact same identifiers as the upserted ones.
    """
    return McpRawItem(
        mcp=_build_mcp_server(
            file_path=file_path,
            server_name=server_name,
            server_config=server_config,
            blob_sha=blob_sha,
        ),
        repository=repository,
        branch=branch,
        organization=organization,
    ).model_dump(by_alias=True)
