from typing import Any

from loguru import logger

from integration import ObjectKind
from port_ocean.context.ocean import ocean


@ocean.on_resync(ObjectKind.DUMMY)
async def resync_dummy(kind: str) -> list[dict[str, Any]]:
    logger.info(f"Resyncing dummy kind {kind}")
    return [{"id": "dummy-1", "name": "dummy"}]


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting dummy-wiz-scan integration")
