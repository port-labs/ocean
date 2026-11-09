from __future__ import annotations

from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from azure_integration.foundry.core.exporters.agent_versions_exporter import (
    _normalize_agent_version,
)
from azure_integration.foundry.core.exporters.agents_exporter import _normalize_agent
from azure_integration.foundry.core.exporters.conversations_exporter import (
    _normalize_conversation,
)
from azure_integration.foundry.core.exporters.memory_stores_exporter import (
    _normalize_memory_store,
)
from azure_integration.foundry.core.exporters.model_deployments_exporter import (
    _normalize_deployment,
)
from azure_integration.foundry.helpers.scope import enrich_with_project
from azure_integration.foundry.helpers.responses_catalog import (
    normalize_foundry_response,
)
from azure_integration.foundry.kinds import ObjectKind


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
    if kind == ObjectKind.MEMORY_STORE:
        return dict(_normalize_memory_store(raw))
    return dict(raw)


def catalog_delete_stub(kind: str, identifier: str) -> dict[str, Any]:
    """Minimal raw row so unregister mappings resolve the entity identifier."""
    return {"id": identifier, "name": identifier}


async def register_catalog_rows(
    kind: str,
    raws: list[dict[str, Any]],
    run: IntegrationRun | None = None,
) -> bool:
    if not raws:
        return False
    try:
        batch = [
            enrich_with_project(normalize_catalog_payload(kind, raw)) for raw in raws
        ]
        await ocean.integration.port_app_config_handler.get_port_app_config(
            use_cache=False
        )
        async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
            await ocean.register_raw(kind, batch)
        return True
    except Exception as error:
        message = (
            f"Failed to upsert {len(raws)} {kind} entit(y/ies) into the catalog "
            f"(continuing): {error}"
        )
        logger.warning(message)
        if run is not None:
            await ocean.port_client.post_run_log(
                run, message, level="WARNING", should_raise=False
            )
        return False


async def unregister_catalog_rows(
    kind: str,
    raws: list[dict[str, Any]],
    run: IntegrationRun | None = None,
) -> None:
    if not raws:
        return
    try:
        batch = [
            enrich_with_project(normalize_catalog_payload(kind, raw)) for raw in raws
        ]
        await ocean.integration.port_app_config_handler.get_port_app_config(
            use_cache=False
        )
        async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
            await ocean.unregister_raw(kind, batch)
    except Exception as error:
        message = (
            f"Failed to delete {len(raws)} {kind} entit(y/ies) from the catalog "
            f"(continuing): {error}"
        )
        logger.warning(message)
        if run is not None:
            await ocean.port_client.post_run_log(
                run, message, level="WARNING", should_raise=False
            )
