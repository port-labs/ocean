import enum
import http

from fastapi import Response
from loguru import logger
from gcp_core.gcp_client import GCP_PUBSUB_TOPIC_ASSET_KIND, ResourceNotFoundError
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from starlette.requests import Request

from gcp_core.utils import (
    GotFeedCreatedSuccessfullyMessage,
    create_gcp_client_from_ocean_config,
    parse_feed_event_from_request,
)


class AssetTypesWithSpecialHandling(enum.StrEnum):
    TOPIC = GCP_PUBSUB_TOPIC_ASSET_KIND


@ocean.on_resync(kind=GCP_PUBSUB_TOPIC_ASSET_KIND)
async def resync_topics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(kind=kind):
        gcp_client = create_gcp_client_from_ocean_config()
        async for topics in gcp_client.generate_topics():
            yield topics


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    # List of supported assets: https://cloud.google.com/asset-inventory/docs/supported-asset-types
    with logger.contextualize(kind=kind):
        if kind in iter(AssetTypesWithSpecialHandling):
            logger.debug("Kind already has a specific handling, skipping")
            return
        gcp_client = create_gcp_client_from_ocean_config()
        async for resources in gcp_client.generate_resources(kind):
            yield resources


@ocean.router.post("/events")
async def feed_events_callback(request: Request) -> Response:
    gcp_client = create_gcp_client_from_ocean_config()
    try:
        feed_event = await parse_feed_event_from_request(request)
        with logger.contextualize(**feed_event.metadata):
            resource = await gcp_client.get_resource(
                feed_event.asset_name, feed_event.asset_type
            )
            if feed_event.asset_type == GCP_PUBSUB_TOPIC_ASSET_KIND:
                resource = await gcp_client.get_pubsub_topic(
                    feed_event.asset_name, resource["project"]
                )
            logger.info("Got Cloud Asset Inventory Feed event")
            if (
                "deleted" in feed_event.data.keys()
                and feed_event.data["deleted"] is True
            ):
                await ocean.unregister_raw(feed_event.asset_type, [resource])
            else:
                await ocean.register_raw(feed_event.asset_type, [resource])
    except ResourceNotFoundError:
        logger.warning(f"Didn't find any resource named: {feed_event.asset_name}")
        return Response(status_code=http.HTTPStatus.NOT_FOUND)
    except GotFeedCreatedSuccessfullyMessage:
        logger.info("Feed has been created successfully.")
        return Response(status_code=http.HTTPStatus.OK)
    except Exception as e:
        logger.error(
            f"Got error while processing Feed event {feed_event.message_id}: {str(e)}"
        )
    return Response(status_code=http.HTTPStatus.OK)
