from __future__ import annotations

from typing import Any

from azure_integration.foundry.helpers.utils import deep_merge


def latest_agent_definition(agent: dict[str, Any]) -> dict[str, Any]:
    """Latest definition from a Foundry agent GET payload."""
    versions = agent.get("versions")
    if isinstance(versions, dict):
        latest = versions.get("latest")
        if isinstance(latest, dict):
            definition = latest.get("definition")
            if isinstance(definition, dict):
                return dict(definition)
    definition = agent.get("definition")
    return dict(definition) if isinstance(definition, dict) else {}


def definition_kind(body: dict[str, Any]) -> str | None:
    definition = body.get("definition")
    return definition.get("kind") if isinstance(definition, dict) else None


def foundry_features_header(kind: object) -> dict[str, str] | None:
    if not isinstance(kind, str):
        return None
    feature = {
        "hosted": "HostedAgents=V1Preview",
        "workflow": "WorkflowAgents=V1Preview",
        "external": "ExternalAgents=V1Preview",
        "voice": "VoiceAgents=V1Preview",
    }.get(kind)
    return {"Foundry-Features": feature} if feature else None


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
    if definition["kind"] == "prompt":
        definition["model"] = model
        if instructions is not None:
            definition["instructions"] = instructions
    return body


def build_update_agent_body(
    *,
    model: str | None = None,
    instructions: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Partial update payload; executor merges over GET before POST."""
    body = deep_merge({}, config or {})
    definition = body.get("definition")
    if not isinstance(definition, dict):
        definition = {}
        body["definition"] = definition

    kind = definition.get("kind")
    if kind in (None, "prompt"):
        if model is not None:
            definition["model"] = model
        if instructions is not None:
            definition["instructions"] = instructions
    return body
