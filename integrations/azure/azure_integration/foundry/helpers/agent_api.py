from __future__ import annotations

from typing import Any

from azure_integration.foundry.helpers.utils import deep_merge


def build_create_agent_body(
    *,
    name: str,
    model: str,
    instructions: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Foundry create-agent payload.

    First-class fields always win. ``config`` is deep-merged underneath so callers
    can pass through API fields we do not model (tools, description, metadata,
    rai_config, hosted/workflow kind, etc.).
    """
    body = deep_merge({"definition": {"kind": "prompt"}}, config or {})
    definition = body.get("definition")
    if not isinstance(definition, dict):
        definition = {}
        body["definition"] = definition

    body["name"] = name
    definition["kind"] = definition.get("kind") or "prompt"
    definition["model"] = model
    if instructions is not None:
        definition["instructions"] = instructions
    return body


def build_update_agent_body(
    *,
    name: str | None = None,
    model: str | None = None,
    instructions: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Foundry update-agent payload with the same config passthrough rules."""
    body = deep_merge({}, config or {})
    if name is not None:
        body["name"] = name

    definition_overlay: dict[str, Any] = {}
    if model is not None:
        definition_overlay["model"] = model
    if instructions is not None:
        definition_overlay["instructions"] = instructions
    if definition_overlay:
        existing = body.get("definition")
        if isinstance(existing, dict):
            body["definition"] = deep_merge(existing, definition_overlay)
        else:
            body["definition"] = definition_overlay
    return body
