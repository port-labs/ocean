from __future__ import annotations

from loguru import logger
from port_ocean.context.ocean import ocean

from plain.client import PlainClient


async def register_webhook_target() -> None:
    base_url = ocean.app.base_url
    if not base_url:
        logger.warning(
            "Skipping Plain webhook registration because OCEAN__BASE_URL is not set"
        )
        return

    client = PlainClient()
    await client.ensure_webhook_target(base_url)
