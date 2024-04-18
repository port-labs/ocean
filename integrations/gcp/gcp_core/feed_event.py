import base64
import json
from typing import Any

from port_ocean.core.ocean_types import RAW_ITEM

from gcp_core.errors import (
    AssetHasNoProjectAncestorError,
    GotFeedCreatedSuccessfullyMessageError,
)

from .search.searches import (
    get_folder,
    get_organization,
    get_project,
    get_topic,
    search_resource,
)
from .utils import EXTRA_PROJECT_FIELD, AssetTypesWithSpecialHandling


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
            # Couldn't create a valid data structure, raising error
            raise GotFeedCreatedSuccessfullyMessageError()
        raise e
    return asset_data

