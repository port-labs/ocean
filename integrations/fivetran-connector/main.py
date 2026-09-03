import asyncio
import typing

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from fivetran_connector.client import FivetranClient
from integration import FivetranIntegration, FivetranResourceConfig  # noqa: F401


async def _get_id_token(audience: str) -> typing.Optional[str]:
    import google.auth.transport.requests
    import google.oauth2.id_token

    try:
        request = google.auth.transport.requests.Request()
        return await asyncio.to_thread(
            google.oauth2.id_token.fetch_id_token, request, audience
        )
    except Exception as e:
        logger.debug(f"GCP ID token unavailable for {audience!r}: {e}")
        return None


@ocean.on_resync()
async def resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = typing.cast(FivetranResourceConfig, event.resource_config)
    function_url = config.selector.function_url
    secrets = config.selector.secrets
    agent = f"fivetran-connector/{ocean.config.integration.identifier}"

    async def _token_supplier() -> typing.Optional[str]:
        return await _get_id_token(function_url)

    client = FivetranClient(
        agent=agent,
        function_url=function_url,
        secrets=secrets,
        token_supplier=_token_supplier,
    )
    logger.info(f"Syncing kind={kind!r} via Fivetran connector at {function_url!r}")
    async for page in client.sync(kind):
        yield page
