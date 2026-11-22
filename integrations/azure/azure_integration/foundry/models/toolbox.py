from __future__ import annotations

import re
from typing import Any

from pydantic import Field

from azure_integration.foundry.models.base import FoundryModel

PORT_MCP_SERVER_LABEL = "port"
GITHUB_MCP_SERVER_LABEL = "github"
TOOLBOX_SERVER_LABEL = "port-mcps"
_TOOLBOX_RE = re.compile(r"/toolboxes/([^/]+)/")
_MANAGED = frozenset({TOOLBOX_SERVER_LABEL, PORT_MCP_SERVER_LABEL})


class Tool(FoundryModel):
    # Foundry MCP tool fields are snake_case (no Port camel aliases).
    type: str | None = None
    server_label: str | None = None
    server_url: str | None = None
    require_approval: str | None = None
    project_connection_id: str | None = None

    @property
    def key(self) -> tuple[Any, ...]:
        return (
            self.type,
            self.server_label,
            self.server_url,
            self.project_connection_id,
        )

    @property
    def is_managed(self) -> bool:
        return self.type == "mcp" and self.server_label in _MANAGED

    @property
    def toolbox_name(self) -> str | None:
        if self.type != "mcp" or not self.server_url:
            return None
        match = _TOOLBOX_RE.search(self.server_url)
        return match.group(1) if match else None


class ToolboxLatest(FoundryModel):
    version: str
    tools: list[Tool] = Field(default_factory=list)

    def contains_all(self, desired: list[Tool]) -> bool:
        have = {t.key for t in self.tools}
        return all(t.key in have for t in desired)

    def merge(self, desired: list[Tool]) -> list[dict[str, Any]]:
        have = {t.key for t in self.tools}
        return [
            *(t.model_dump() for t in self.tools),
            *(t.model_dump() for t in desired if t.key not in have),
        ]


def parse_toolbox_latest(payload: dict) -> ToolboxLatest | None:
    versions = payload.get("versions")
    latest = versions.get("latest") if isinstance(versions, dict) else None
    if not isinstance(latest, dict):
        return None
    try:
        return ToolboxLatest.model_validate(latest)
    except Exception:
        return None
