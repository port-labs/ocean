from __future__ import annotations

from typing import Any


def build_create_agent_body(
    *,
    name: str,
    model: str,
    instructions: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition: dict[str, Any] = {"kind": "prompt", "model": model}
    if instructions:
        definition["instructions"] = instructions
    body: dict[str, Any] = {"name": name, "definition": definition}
    if metadata:
        body["metadata"] = metadata
    return body


def build_update_agent_body(
    *,
    name: str | None = None,
    model: str | None = None,
    instructions: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    definition: dict[str, Any] = {}
    if model is not None:
        definition["model"] = model
    if instructions is not None:
        definition["instructions"] = instructions
    if definition:
        body["definition"] = definition
    if metadata is not None:
        body["metadata"] = metadata
    return body
