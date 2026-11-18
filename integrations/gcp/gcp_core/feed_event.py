import base64
import json
from typing import Any

from loguru import logger


from gcp_core.errors import (
    AssetHasNoProjectAncestorError,
    GotFeedCreatedSuccessfullyMessageError,
)


def get_project_name_from_ancestors(ancestors: list[str]) -> str:
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


def is_iam_policy_event(asset_data: dict[str, Any]) -> bool:
    """Whether this came from a content-type=iam-policy feed rather than a content-type=resource one.

    Keyed on the absence of `resource` rather than the presence of `iamPolicy`: a policy cleared of
    every binding arrives with neither, and `feed_event_to_resource` would still index `resource`.
    `priorAsset` is checked too, because a deleted resource carries its data only there.
    """
    return not any(
        "resource" in (asset_data.get(key) or {}) for key in ("asset", "priorAsset")
    )


def canonical_resource_name(
    feed_asset_name: str, assets: list[dict[str, Any]]
) -> str | None:
    """The name `searchAllIamPolicies` uses for the asset a feed event calls `feed_asset_name`."""
    for asset in assets:
        if asset["name"] == feed_asset_name:
            return str(asset["name"])

    # An alias replaces the final segment of the name and nothing else, so rebuild the candidate and
    # compare whole strings: a free-text attribute cannot collide its way to a match.
    anchored = [
        str(asset["name"])
        for asset in assets
        if any(
            f"{str(asset['name']).rsplit('/', 1)[0]}/{alias}" == feed_asset_name
            for alias in asset["aliases"]
        )
    ]
    if len(anchored) == 1:
        return anchored[0]

    # Several assets share an alias (every asset reports the same project number), so the feed's
    # name does not identify one. Refusing beats guessing: a wrong name is an entity no resync
    # reconciles away, where no name only waits for the next resync.
    if anchored:
        logger.warning(
            f"{feed_asset_name} matches {len(anchored)} assets by alias; refusing to guess"
        )
    return None
