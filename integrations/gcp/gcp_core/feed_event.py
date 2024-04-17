import base64
import json
from typing import Any, NotRequired, TypedDict
from fastapi import Request

from .search.searches import (
    get_folder,
    get_organization,
    get_project,
    get_topic,
    search_resource,
)
from .search.utils import EXTRA_PROJECT_FIELD, AssetTypesWithSpecialHandling
from port_ocean.core.ocean_types import RAW_ITEM


class FeedEvent(TypedDict):
    message_id: str
    asset_name: str
    asset_type: str
    project_id: NotRequired[str]
    data: dict[Any, Any]


class GotFeedCreatedSuccessfullyMessage(Exception):
    pass


def get_project_from_ancestors(ancestors: list[str]) -> str | None:
    for ancestor in ancestors:
        if ancestor.startswith("projects/"):
            return ancestor
    return None


async def parse_feed_event_from_request(
    request: Request,
) -> FeedEvent:
    # The message schema: https://cloud.google.com/pubsub/docs/push?_gl=1*thv8i4*_ga*NDQwMTA2MzM5LjE3MTEyNzQ2MDY.*_ga_WH2QY8WWF5*MTcxMzA3NzU3Ni40My4xLjE3MTMwNzgxMjUuMC4wLjA.&_ga=2.161162040.-440106339.1711274606&_gac=1.184150868.1711468720.CjwKCAjw5ImwBhBtEiwAFHDZx1mm-z19UdKpEARcG2-F_TXXbXw7j7_gVPKiQ9Z5KcpsvXF1fFb_MBoCUFkQAvD_BwE#receive_push
    request_json = await request.json()
    message_id = request_json["message"]["messageId"]
    try:
        data = base64.b64decode(request_json["message"]["data"])
        asset_data = json.loads(data)
    except json.JSONDecodeError as e:
        if data.decode("utf-8").startswith(
            "You have successfully configured real time feed"
        ):
            raise GotFeedCreatedSuccessfullyMessage()
        raise e
    # The Asset schema: https://cloud.google.com/asset-inventory/docs/monitoring-asset-changes#creating_feeds
    asset_type = asset_data["asset"]["assetType"]
    asset_name = asset_data["asset"]["name"]
    asset_project = get_project_from_ancestors(asset_data["asset"]["ancestors"])
    feed_event = FeedEvent(
        message_id=message_id,
        asset_name=asset_name,
        asset_type=asset_type,
        data=asset_data,
    )
    if asset_project:
        feed_event["project_id"] = asset_project
    return feed_event


async def feed_event_to_resource(feed_event: FeedEvent) -> RAW_ITEM:
    resource = None
    if feed_event["asset_type"] == AssetTypesWithSpecialHandling.TOPIC:
        resource = await get_topic(feed_event["asset_name"])
        project_id = feed_event["project_id"]
        resource[EXTRA_PROJECT_FIELD] = await get_project(project_id)
    elif feed_event["asset_type"] == AssetTypesWithSpecialHandling.FOLDER:
        resource = await get_folder(feed_event["asset_name"])
    elif feed_event["asset_type"] == AssetTypesWithSpecialHandling.ORGANIZATION:
        resource = await get_organization(feed_event["asset_name"])
    elif feed_event["asset_type"] == AssetTypesWithSpecialHandling.PROJECT:
        resource = await get_project(feed_event["asset_name"])
    else:
        resource = await search_resource(
            feed_event["project_id"], feed_event["asset_type"], feed_event["asset_name"]
        )
    return resource
