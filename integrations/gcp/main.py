import http

from fastapi import Response
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from starlette.requests import Request

from gcp_core.utils import (
    GotFeedCreatedSuccessfullyMessage,
    create_gcp_client_from_ocean_config,
    parse_subscription_message_from_request,
)


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    # List of supported assets: https://cloud.google.com/asset-inventory/docs/supported-asset-types
    gcp_client = create_gcp_client_from_ocean_config()
    with logger.contextualize(kind=kind):
        async for resources in gcp_client.generate_resources(kind):
            yield resources


@ocean.router.post("/events")
async def feed_events_callback(feed_event: Request) -> Response:
    gcp_client = create_gcp_client_from_ocean_config()
    try:
        message = await parse_subscription_message_from_request(feed_event)
        with logger.contextualize(**message.metadata):
            results = [
                resources
                async for resources in gcp_client.generate_resources(
                    message.asset_type, message.asset_name
                )
            ]
            if len(results[0]) == 1:
                resource = results[0][0]
                logger.info("Got Cloud Asset Inventory Feed event")
                if "deleted" in message.data.keys() and message.data["deleted"] is True:
                    await ocean.unregister_raw(message.asset_type, [resource])
                else:
                    await ocean.register_raw(message.asset_type, [resource])
            elif len(results[0]) < 1:
                logger.warning(f"Didn't find any resource named: {message.asset_name}")
                return Response(status_code=http.HTTPStatus.NOT_FOUND)
            else:
                logger.warning(f"Found too many resources named: {message.asset_name}")
                return Response(status_code=http.HTTPStatus.CONFLICT)
    except GotFeedCreatedSuccessfullyMessage:
        logger.info("Feed has been created successfully.")
        return Response(status_code=http.HTTPStatus.OK)
    except Exception as e:
        logger.error(
            f"Got error while processing Feed event {message.message_id}: {str(e)}"
        )
    return Response(status_code=http.HTTPStatus.OK)
