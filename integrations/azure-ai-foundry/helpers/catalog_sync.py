from __future__ import annotations

from typing import Any

from core.exporters.agent_versions_exporter import _normalize_agent_version
from core.exporters.agents_exporter import _normalize_agent
from core.exporters.conversations_exporter import _normalize_conversation
from helpers.responses_catalog import normalize_foundry_response
from core.exporters.model_deployments_exporter import _normalize_deployment
from core.exporters.skills_exporter import _normalize_memory_store, _normalize_skill
from integration import ObjectKind


def normalize_catalog_payload(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Shape Foundry API payloads like resync exporters so JQ mappings apply immediately."""
    if kind == ObjectKind.AGENT:
        return dict(_normalize_agent(raw))
    if kind == ObjectKind.AGENT_VERSION:
        agent_id = str(raw.get("agent_id") or raw.get("agentId") or "")
        return dict(_normalize_agent_version(raw, agent_id))
    if kind == ObjectKind.MODEL_DEPLOYMENT:
        return dict(_normalize_deployment(raw))
    if kind == ObjectKind.CONVERSATION:
        return dict(_normalize_conversation(raw))
    if kind == ObjectKind.RESPONSE:
        normalized = normalize_foundry_response(raw)
        return dict(normalized) if normalized else dict(raw)
    if kind == ObjectKind.SKILL:
        return dict(_normalize_skill(raw))
    if kind == ObjectKind.MEMORY_STORE:
        return dict(_normalize_memory_store(raw))
    return dict(raw)


def catalog_delete_stub(kind: str, identifier: str) -> dict[str, Any]:
    """Minimal raw row so unregister mappings resolve the entity identifier."""
    return {"id": identifier, "name": identifier}
