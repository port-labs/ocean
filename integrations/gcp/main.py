import http

from fastapi import Request, Response
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gcp_core.feed_event import (
    GotFeedCreatedSuccessfullyMessage,
    feed_event_to_resource,
    parse_feed_event_from_request,
)
from gcp_core.search.iterators import iterate_per_available_project
from gcp_core.search.searches import (
    ResourceNotFoundError,
    list_all_topics_per_project,
    search_all_folders,
    search_all_organizations,
    search_all_projects,
    search_all_resources,
)
from gcp_core.search.utils import (
    AssetTypesWithSpecialHandling,
)


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
        async for batch in iterate_per_available_project(list_all_topics_per_project):
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
            kind=feed_event["asset_type"],
            name=feed_event["asset_name"],
            project=feed_event["project_id"],
        ):
            logger.info("Got Real-Time event")
            resource = await feed_event_to_resource(feed_event)
            if feed_event["data"].get("deleted") is True:
                logger.info("Deleting Entity")
                await ocean.unregister_raw(feed_event["asset_type"], [resource])
            else:
                logger.info("Upserting Entity")
                await ocean.register_raw(feed_event["asset_type"], [resource])
    except ResourceNotFoundError:
        logger.exception(f"Didn't find any resource named: {feed_event['asset_name']}")
        return Response(status_code=http.HTTPStatus.NOT_FOUND)
    except GotFeedCreatedSuccessfullyMessage:
        logger.info("Assets Feed created successfully")
    return Response(status_code=200)
