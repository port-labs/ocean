from __future__ import annotations

from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from azure_integration.foundry.helpers.scope import (
    get_project_arm_id,
    get_project_endpoint,
)
from azure_integration.foundry.helpers.utils import enrich_with_project


def catalog_delete_stub(kind: str, identifier: str) -> dict[str, Any]:
    """Minimal raw row so unregister mappings resolve the entity identifier."""
    return {"id": identifier, "name": identifier}


def _enrich_for_catalog(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        endpoint = get_project_endpoint()
    except ValueError:
        return dict(raw)
    return enrich_with_project(
        raw,
        project_endpoint=endpoint,
        project_id=get_project_arm_id(),
    )


async def register_catalog_rows(
    kind: str,
    raws: list[dict[str, Any]],
    run: IntegrationRun | None = None,
) -> bool:
    if not raws:
        return False
    try:
        batch = [_enrich_for_catalog(raw) for raw in raws]
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
        batch = [_enrich_for_catalog(raw) for raw in raws]
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
