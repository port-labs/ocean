from __future__ import annotations

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.exceptions.core import OceanAbortException

from plain.client import PlainClient
from plain.constants import WEBHOOK_PATH_SUFFIX
from plain.exceptions import PlainGraphQLError, PlainHTTPError


async def register_webhook_target() -> None:
    base_url = ocean.app.base_url
    if not base_url:
        logger.warning(
            "Skipping Plain webhook registration because OCEAN__BASE_URL is not set"
        )
        return

    client = PlainClient()
    try:
        await client.ensure_webhook_target(base_url)
    except (OceanAbortException, PlainGraphQLError, PlainHTTPError) as error:
        target_url = f"{base_url.rstrip('/')}{WEBHOOK_PATH_SUFFIX}"
        logger.warning(
            "Could not register the Plain webhook target ({}). "
            "The integration will keep running so you can create it "
            "manually in Plain, pointing at {}. "
            "The API key needs webhookTarget:read, webhookTarget:create, "
            "and webhookTarget:edit.",
            error,
            target_url,
        )
    except httpx.RequestError as error:
        target_url = f"{base_url.rstrip('/')}{WEBHOOK_PATH_SUFFIX}"
        logger.warning(
            "Could not reach Plain API to register webhook target ({}). "
            "The integration will keep running. "
            "You can create the webhook target manually in Plain, pointing at {}.",
            error,
            target_url,
        )
