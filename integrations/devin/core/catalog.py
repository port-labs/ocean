from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun


async def upsert_raw(kind: str, raw: dict[str, Any]) -> None:
    """Register one raw object in the catalog with a machine HTTP event context."""
    await ocean.integration.port_app_config_handler.get_port_app_config(use_cache=False)
    async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
        await ocean.register_raw(kind, [raw])


async def upsert_raw_best_effort(
    kind: str, raw: dict[str, Any], run: IntegrationRun | None = None
) -> None:
    """Best-effort catalog upsert; optional run receives a warning log on failure."""
    try:
        await upsert_raw(kind, raw)
    except Exception as error:
        message = f"Failed to upsert {kind} into the catalog (continuing): {error}"
        logger.warning(message)
        if run is None:
            return
        try:
            await ocean.port_client.post_run_log(run, message, level="WARNING")
        except Exception as log_error:
            logger.warning(
                f"Failed to post run log for catalog upsert failure: {log_error}"
            )
