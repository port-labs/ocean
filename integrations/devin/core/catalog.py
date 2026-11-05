from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean


async def upsert_raw_from_background(kind: str, raw: dict[str, Any]) -> None:
    """Best-effort catalog upsert from a background task with no event context.

    Unlike inside an action run, there is no parent context to inherit a port
    app config from, so `register_raw` fetches it into this fresh context itself.
    """
    try:
        async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
            await ocean.register_raw(kind, [raw])
    except Exception as error:
        logger.warning(f"Failed to upsert {kind} into the catalog: {error}")
