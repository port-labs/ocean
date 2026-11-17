from __future__ import annotations

from typing import Any


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
