from __future__ import annotations

import re
from typing import Any

_A2A_PATH = re.compile(
    r"/api/projects/(?P<project>[^/]+)/agents/(?P<agent>[^/]+)/endpoint/protocols/a2a"
)

_A2A_TOOL_TYPES = frozenset({"a2a", "a2a_preview"})


def parse_foundry_a2a_url(target: str) -> tuple[str | None, str | None]:
    if not target:
        return None, None
    match = _A2A_PATH.search(target)
    if not match:
        return None, None
    return match.group("project"), match.group("agent")


def skill_names_from_refs(skills: list[Any]) -> list[str]:
    names: list[str] = []
    for ref in skills:
        if isinstance(ref, str) and ref:
            names.append(ref)
        elif isinstance(ref, dict):
            name = ref.get("name") or ref.get("id")
            if name:
                names.append(str(name))
    return names


def connection_name_from_ref(conn: str) -> str:
    """Short connection name from a bare id or ARM project-connection resource id."""
    raw = conn.strip().rstrip("/")
    marker = "/connections/"
    if marker in raw:
        return raw.rsplit(marker, 1)[-1]
    return raw


def a2a_connection_ids_from_tools(tools: list[Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        tool_type = tool.get("type") or ""
        if tool_type not in _A2A_TOOL_TYPES:
            continue
        conn = tool.get("project_connection_id") or tool.get("projectConnectionId")
        if not conn:
            continue
        name = connection_name_from_ref(str(conn))
        if name and name not in seen:
            seen.add(name)
            ids.append(name)
    return ids
