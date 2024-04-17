import http

from fastapi import Request, Response
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gcp_core.feed_event import (
    AssetHasNoProjectAncestorError,
    GotFeedCreatedSuccessfullyMessage,
    feed_event_to_resource,
    get_project_from_ancestors,
    parse_asset_data,
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
    """
    This is the real-time events handler. The subscription which is connected to the Feeds Topic will send events here once
    the events are inserted into the Assets Inventory.

    NOTICE that there might be a 10 minute delay here, as documented:
    https://cloud.google.com/asset-inventory/docs/monitoring-asset-changes#limitations

    The request has a message, which contains a 64based data of the asset.
    The message schema: https://cloud.google.com/pubsub/docs/push?_gl=1*thv8i4*_ga*NDQwMTA2MzM5LjE3MTEyNzQ2MDY.*_ga_WH2QY8WWF5*MTcxMzA3NzU3Ni40My4xLjE3MTMwNzgxMjUuMC4wLjA.&_ga=2.161162040.-440106339.1711274606&_gac=1.184150868.1711468720.CjwKCAjw5ImwBhBtEiwAFHDZx1mm-z19UdKpEARcG2-F_TXXbXw7j7_gVPKiQ9Z5KcpsvXF1fFb_MBoCUFkQAvD_BwE#receive_push
    The Asset schema: https://cloud.google.com/asset-inventory/docs/monitoring-asset-changes#creating_feeds
    """

    request_json = await request.json()
    try:
        asset_data = await parse_asset_data(request_json["message"]["data"])
        asset_type = asset_data["asset"]["assetType"]
        asset_name = asset_data["asset"]["name"]
        asset_project = get_project_from_ancestors(asset_data["asset"]["ancestors"])
        logging_mapping = {
            "asset_type": asset_type,
            "asset_name": asset_name,
            "asset_project": asset_project,
        }
        logger.info("Got Real-Time event", **logging_mapping)
        resource = await feed_event_to_resource(
            asset_type=asset_type, project_id=asset_project, asset_name=asset_name
        )
        if asset_data.get("deleted") is True:
            logger.info("Deleting Entity", **logging_mapping)
            await ocean.unregister_raw(asset_type, [resource])
        else:
            logger.info("Upserting Entity", **logging_mapping)
            await ocean.register_raw(asset_type, [resource])
    except AssetHasNoProjectAncestorError:
        logger.exception(f"Couldn't find project ancestor to asset {asset_name}")
    except ResourceNotFoundError:
        logger.exception(f"Didn't find any {asset_type} resource named: {asset_name}")
        return Response(status_code=http.HTTPStatus.NOT_FOUND)
    except GotFeedCreatedSuccessfullyMessage:
        logger.info("Assets Feed created successfully")
    return Response(status_code=200)
