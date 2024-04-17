import base64
import json
from typing import Any, NotRequired, TypedDict

from port_ocean.core.ocean_types import RAW_ITEM

from .search.searches import (
    get_folder,
    get_organization,
    get_project,
    get_topic,
    search_resource,
)
from .search.utils import EXTRA_PROJECT_FIELD, AssetTypesWithSpecialHandling


class FeedEvent(TypedDict):
    message_id: str
    asset_name: str
    asset_type: str
    project_id: NotRequired[str]
    data: dict[Any, Any]


class GotFeedCreatedSuccessfullyMessage(Exception):
    pass


class AssetHasNoProjectAncestorError(Exception):
    pass


def get_project_from_ancestors(ancestors: list[str]) -> str:
    for ancestor in ancestors:
        if ancestor.startswith("projects/"):
            return ancestor
    raise AssetHasNoProjectAncestorError


async def parse_asset_data(encoded_data: str) -> dict[str, Any]:
    try:
        data = base64.b64decode(encoded_data)
        asset_data = json.loads(data)
    except json.JSONDecodeError as e:
        if data.decode("utf-8").startswith(
            "You have successfully configured real time feed"
        ):
            raise GotFeedCreatedSuccessfullyMessage()
        raise e
    return asset_data


async def feed_event_to_resource(
    asset_type: str, asset_name: str, project_id: str
) -> RAW_ITEM:
    resource = None
    if asset_type == AssetTypesWithSpecialHandling.TOPIC:
        resource = await get_topic(asset_name)
        resource[EXTRA_PROJECT_FIELD] = await get_project(project_id)
    elif asset_type == AssetTypesWithSpecialHandling.FOLDER:
        resource = await get_folder(asset_name)
    elif asset_type == AssetTypesWithSpecialHandling.ORGANIZATION:
        resource = await get_organization(asset_name)
    elif asset_type == AssetTypesWithSpecialHandling.PROJECT:
        resource = await get_project(asset_name)
    else:
        resource = await search_resource(project_id, asset_type, asset_name)
    return resource
