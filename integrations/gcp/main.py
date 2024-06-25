import base64
import http
import os
import tempfile
import typing

from fastapi import Request, Response
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gcp_core.errors import (
    AssetHasNoProjectAncestorError,
    GotFeedCreatedSuccessfullyMessageError,
    ResourceNotFoundError,
)
from gcp_core.feed_event import get_project_name_from_ancestors, parse_asset_data
from gcp_core.overrides import GCPCloudResourceSelector
from gcp_core.search.iterators import iterate_per_available_project
from gcp_core.search.resource_searches import (
    feed_event_to_resource,
    list_all_topics_per_project,
    search_all_folders,
    search_all_organizations,
    search_all_projects,
    search_all_resources,
)
from gcp_core.utils import (
    AssetTypesWithSpecialHandling,
    get_current_resource_config,
)


def _resolve_resync_method_for_resource(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    match kind:
        case AssetTypesWithSpecialHandling.TOPIC:
            return iterate_per_available_project(list_all_topics_per_project)
        case AssetTypesWithSpecialHandling.FOLDER:
            return search_all_folders()
        case AssetTypesWithSpecialHandling.ORGANIZATION:
            return search_all_organizations()
        case AssetTypesWithSpecialHandling.PROJECT:
            return search_all_projects()
        case _:
            return iterate_per_available_project(search_all_resources, asset_type=kind)


@ocean.on_start()
async def setup_application_default_credentials() -> None:
    if not ocean.integration_config["encoded_adc_configuration"]:
        logger.info(
            "Using integration's environment Application Default Credentials configuration"
        )
        return
    b64_credentials = ocean.integration_config["encoded_adc_configuration"]
    credentials_json = base64.b64decode(b64_credentials).decode("utf-8")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
        temp_file.write(credentials_json.encode("utf-8"))
        credentials_path = temp_file.name

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    logger.info("Created Application Default Credentials configuration")


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in search_all_folders():
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.ORGANIZATION)
async def resync_organizations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in search_all_organizations():
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in search_all_projects():
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.TOPIC)
async def resync_topics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in iterate_per_available_project(list_all_topics_per_project):
        yield batch


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in iter(AssetTypesWithSpecialHandling):
        logger.debug("Kind already has a specific handling, skipping")
        return
    async for batch in iterate_per_available_project(
        search_all_resources, asset_type=kind
    ):
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.CLOUD_RESOURCE)
async def resync_cloud_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    resource_kinds = typing.cast(
        GCPCloudResourceSelector, get_current_resource_config().selector
    ).resource_kinds
    for resource_kind in resource_kinds:
        logger.info(
            f"Found Cloud Resource kind {resource_kind}, finding relevant resources.."
        )
        iterator_resync_method = _resolve_resync_method_for_resource(resource_kind)
        async for resources_batch in iterator_resync_method:
            yield resources_batch


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
        asset_project = get_project_name_from_ancestors(
            asset_data["asset"]["ancestors"]
        )
        with logger.contextualize(
            asset_type=asset_type, asset_name=asset_name, asset_project=asset_project
        ):
            logger.info("Got Real-Time event")
            resource = await feed_event_to_resource(
                asset_type=asset_type, project_id=asset_project, asset_name=asset_name
            )
            if asset_data.get("deleted") is True:
                logger.info("Registering a deleted resource")
                await ocean.unregister_raw(asset_type, [resource])
            else:
                logger.info("Registering a change in the data")
                await ocean.register_raw(asset_type, [resource])
    except AssetHasNoProjectAncestorError:
        logger.exception(
            f"Couldn't find project ancestor to asset {asset_name}. Other types of ancestors and not supported yet."
        )
    except ResourceNotFoundError:
        logger.warning(
            f"Didn't find any {asset_type} resource named: {asset_name}. Deleting ocean entity."
        )
        await ocean.unregister(
            [
                Entity(
                    blueprint=asset_type,
                    identifier=asset_name,
                )
            ]
        )
        return Response(status_code=http.HTTPStatus.NOT_FOUND)
    except GotFeedCreatedSuccessfullyMessageError:
        logger.info("Assets Feed created successfully")
    except Exception:
        logger.exception("Got error while handling a real time event")
        return Response(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR)
    return Response(status_code=200)
