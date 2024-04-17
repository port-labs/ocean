from fastapi import Request, Response
from loguru import logger

from gcp_core.iterators import iterate_per_available_project
from gcp_core.searches import (
    search_all_folders,
    search_all_organizations,
    search_all_projects,
    search_all_resources,
    search_all_topics,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gcp_core.utils import AssetTypesWithSpecialHandling, parse_feed_event_from_request


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(kind=AssetTypesWithSpecialHandling.FOLDER):
        async for batch in search_all_folders():
            yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.ORGANIZATION)
async def resync_organizations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(kind=AssetTypesWithSpecialHandling.ORGANIZATION):
        async for batch in search_all_organizations():
            yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(kind=AssetTypesWithSpecialHandling.PROJECT):
        async for batch in search_all_projects():
            yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.TOPIC)
async def resync_topics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(kind=AssetTypesWithSpecialHandling.TOPIC):
        async for batch in iterate_per_available_project(search_all_topics):
            yield batch


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    # List of supported assets: https://cloud.google.com/asset-inventory/docs/supported-asset-types
    if kind in iter(AssetTypesWithSpecialHandling):
        logger.debug("Kind already has a specific handling, skipping")
        return
    with logger.contextualize(kind=kind):
        async for batch in iterate_per_available_project(
            search_all_resources, asset_type=kind
        ):
            yield batch


@ocean.router.post("/events")
async def feed_events_callback(request: Request) -> Response:
    try:
        feed_event = await parse_feed_event_from_request(request)
        with logger.contextualize(
            message_id=feed_event["message_id"],
            asset_name=feed_event["asset_name"],
            asset_type=feed_event["asset_type"],
        ):
            resource = await gcp_client.get_single_resource(
                feed_event["asset_name"], feed_event["asset_type"]
            )
            if feed_event["asset_type"] == AssetTypesWithSpecialHandling.TOPIC:
                resource = await gcp_client.get_pubsub_topic(
                    feed_event["asset_name"], resource["project"]
                )
            logger.info("Got Cloud Asset Inventory Feed event")
            if feed_event["data"].get("deleted") is True:
                await ocean.unregister_raw(feed_event["asset_type"], [resource])
            else:
                await ocean.register_raw(feed_event["asset_type"], [resource])
    except ResourceNotFoundError:
        logger.warning(f"Didn't find any resource named: {feed_event['asset_name']}")
        return Response(status_code=http.HTTPStatus.NOT_FOUND)
    except GotFeedCreatedSuccessfullyMessage:
        logger.info("Feed has been created successfully.")
    except Exception:
        logger.exception(
            f"Got error while processing Feed event {feed_event['message_id']}"
        )
    return Response(status_code=http.HTTPStatus.OK)
