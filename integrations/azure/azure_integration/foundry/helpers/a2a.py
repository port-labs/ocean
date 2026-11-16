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
        if conn and conn not in seen:
            seen.add(str(conn))
            ids.append(str(conn))
    return ids
