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


def build_agent_responses_invoke(
    *,
    agent_id: str,
    user_input: str,
    conversation_id: str | None = None,
    extra_body: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Return (path, query_params, json_body) for agent Responses invoke."""
    path = f"agents/{agent_id}/endpoint/protocols/openai/responses"
    body: dict[str, Any] = {"input": user_input, **(extra_body or {})}
    if conversation_id:
        body.setdefault("conversation", conversation_id)
    return path, {}, body
