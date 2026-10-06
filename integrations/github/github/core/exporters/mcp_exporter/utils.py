from __future__ import annotations

from typing import Any, Iterator, Optional

from pydantic import BaseModel, Field

DEFAULT_MCP_PATHS: list[str] = [
    "mcp.json",
    ".mcp.json",
]

REDACTED_VALUE = "***REDACTED***"

_SENSITIVE_KEY_MARKERS = (
    "token",
    "secret",
    "api_key",
    "api-key",
    "apiKey",
    "password",
    "passwd",
    "key",
    "auth",
    "credential",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def _redact_sensitive(value: Any) -> Any:
    """Mask values whose key looks like a credential (token/secret/password/apiKey/...).

    MCP server blocks routinely carry live credentials in `headers`/`env` (and
    sometimes flat on the server object itself), so this is applied recursively
    to everything we emit — including the raw `config` passthrough — rather
    than trusting callers to opt in.
    """
    if isinstance(value, dict):
        return {
            k: (
                REDACTED_VALUE
                if isinstance(v, str) and _is_sensitive_key(k)
                else _redact_sensitive(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive(v) for v in value]
    return value


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
    ## Build a normalized MCP server entry from the raw config.
    raw_url = server_config.get("url")
    url = raw_url if isinstance(raw_url, str) else None
    raw_command = server_config.get("command")
    command = raw_command if isinstance(raw_command, str) else None
    raw_args = server_config.get("args")
    args = raw_args if isinstance(raw_args, list) else []
    raw_headers = server_config.get("headers")
    headers = _redact_sensitive(raw_headers) if isinstance(raw_headers, dict) else {}
    raw_env = server_config.get("env")
    env = _redact_sensitive(raw_env) if isinstance(raw_env, dict) else {}

    return McpServer(
        name=server_name,
        transport="http" if url else "stdio",
        url=url,
        command=command,
        args=args,
        headers=headers,
        env=env,
        config=_redact_sensitive(server_config),
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
