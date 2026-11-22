import base64
import enum
import json
from typing import Any

from loguru import logger
from pydantic.v1 import BaseModel, Field

from gcp_core.errors import (
    AssetHasNoProjectAncestorError,
    GotFeedCreatedSuccessfullyMessageError,
)


class FeedContent(enum.StrEnum):
    """The `--content-type` of the Cloud Asset Inventory feed an event came from.

    An event carries its payload under the field named after the content type, so the field that
    is present is what identifies the feed. Only the two the integration consumes are listed; a
    feed created with any of the other four (orgPolicy, accessPolicy, osInventory, relationship)
    is left unclaimed rather than silently handled as one of these: core then logs
    `Unknown webhook event type received` and raises WebhookEventNotSupportedError, one warning
    and one traceback per event, which is the signal that a feed is publishing what we do not read.
    """

    RESOURCE = "resource"
    IAM_POLICY = "iamPolicy"


class FeedAsset(BaseModel):
    """One side of a feed event. Every field is optional because GCP omits what does not apply:
    a delete carries the asset's data only on `priorAsset`, which has no ancestors."""

    name: str = ""
    asset_type: str = Field("", alias="assetType")
    ancestors: list[str] = []
    resource: dict[str, Any] | None = None
    iam_policy: dict[str, Any] | None = Field(None, alias="iamPolicy")

    class Config:
        allow_population_by_field_name = True

    @property
    def content(self) -> FeedContent | None:
        if self.resource is not None:
            return FeedContent.RESOURCE
        if self.iam_policy is not None:
            return FeedContent.IAM_POLICY
        return None

    @property
    def resource_data(self) -> dict[str, Any]:
        return (self.resource or {})["data"]


class FeedEvent(BaseModel):
    """A Cloud Asset Inventory TemporalAsset, as the feed's Pub/Sub message carries it.

    https://cloud.google.com/asset-inventory/docs/reference/rest/v1/TemporalAsset
    """

    asset: FeedAsset = Field(default_factory=FeedAsset)
    prior_asset: FeedAsset = Field(default_factory=FeedAsset, alias="priorAsset")
    deleted: bool = False

    class Config:
        allow_population_by_field_name = True

    @property
    def content(self) -> FeedContent | None:
        """Which feed produced this. A delete carries its content only on `priorAsset`.

        Unclassified when neither side carries a content field. A policy cleared of every binding
        reaches us through `priorAsset`, except where `priorAssetState` is INVALID or UNSPECIFIED
        (TemporalAsset.PriorAssetState: "Failed to set prior_asset" / "not applicable"), which
        leaves nothing to key on and the change waits for the next resync.
        """
        return self.asset.content or self.prior_asset.content


def get_project_name_from_ancestors(ancestors: list[str]) -> str:
    for ancestor in ancestors:
        if ancestor.startswith("projects/"):
            return ancestor
    raise AssetHasNoProjectAncestorError


async def parse_feed_event(encoded_data: str) -> FeedEvent:
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
    return FeedEvent.parse_obj(asset_data)


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
