import http

from fastapi import Response
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from starlette.requests import Request

from gcp_core.gcp_client import GCPClient
from gcp_core.utils import (
    create_feed_from_ocean_config,
    parseSubscriptionMessageFromRequest,
)


@ocean.on_start()
async def setup_feed() -> None:
    gcp_client = GCPClient.create_from_ocean_config()
    try:
        feed = create_feed_from_ocean_config()
        await gcp_client.create_assets_feed_if_not_exists(feed)
    except Exception as e:
        logger.warning(
            f"Couldn't setup feed, continuing integration without real-time events. Error: {str(e)}"
        )


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    # List of supported assets: https://cloud.google.com/asset-inventory/docs/supported-asset-types
    gcp_client = GCPClient.create_from_ocean_config()
    async for resources in gcp_client.generate_resources(kind):
        logger.info(f"Generating {len(resources)} {kind}'s")
        yield resources


@ocean.router.post("/events")
async def feed_events_callback(feed_event: Request) -> Response:
    gcp_client = GCPClient.create_from_ocean_config()
    message = await parseSubscriptionMessageFromRequest(feed_event)
    try:
        results = [
            resources
            async for resources in gcp_client.generate_resources(
                message.asset_type, message.asset_name
            )
        ]
        if len(results[0]) == 1:
            resource = results[0][0]
            logger.info("Got Cloud Asset Inventory Feed event", **message.metadata)
            logger.info(resource)
            if "deleted" in message.data.keys() and message.data["deleted"] is True:
                await ocean.unregister_raw(message.asset_type, [resource])
            else:
                await ocean.register_raw(message.asset_type, [resource])
        elif len(results[0]) < 1:
            logger.warning(
                f"Didn't find any resource named: {message.asset_name}",
                **message.metadata,
            )
            return Response(status_code=http.HTTPStatus.NOT_FOUND)
        else:
            logger.warning(
                f"Found too many resources named: {message.asset_name}",
                **message.metadata,
            )
            return Response(status_code=http.HTTPStatus.CONFLICT)
    except Exception as e:
        logger.error(
            f"Got error while processing Feed event {message.message_id}: {str(e)}",
            **message.metadata,
        )
    return Response(status_code=http.HTTPStatus.OK)
