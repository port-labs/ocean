from typing import Any, AsyncGenerator, Optional

from google.api_core.exceptions import PermissionDenied
from google.cloud.asset_v1 import (
    AssetServiceAsyncClient,
    ContentType,
    ListFeedsRequest,
)
from google.cloud.asset_v1.services.asset_service import pagers
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from gcp_core.types import CloudAssetInventoryFeed
from gcp_core.utils import parseProtobufMessages

RESOURCE_METADATA_CONTENT_TYPE = ContentType(1)


class GCPClient:
    def __init__(self, parent: str, service_account_file: str) -> None:
        self.async_assets_client: AssetServiceAsyncClient = (
            AssetServiceAsyncClient.from_service_account_file(service_account_file)
        )
        self._parent = parent

    @classmethod
    def create_from_ocean_config(cls) -> "GCPClient":
        if cache := event.attributes.get("gcp_client"):
            return cache
        try:
            parent = ocean.integration_config["parent"]
            service_account = ocean.integration_config["service_account_file_location"]
        except KeyError as e:
            raise KeyError(f"Missing required integration key: {str(e)}")
        gcp_client = cls(parent, service_account)
        event.attributes["gcp_client"] = gcp_client
        return gcp_client

    async def generate_resources(
        self, asset_type: str, asset_name: Optional[str] = None
    ) -> AsyncGenerator[list[dict[Any, Any]], Any]:
        try:
            search_all_resources_request = {
                "scope": self._parent,
                "asset_types": [asset_type],
                "read_mask": "*",
            }
            if asset_name:
                search_all_resources_request["query"] = f"name={asset_name}"
            paginated_responses: pagers.SearchAllResourcesAsyncPager = (
                await self.async_assets_client.search_all_resources(
                    search_all_resources_request
                )
            )
            async for paginated_response in paginated_responses.pages:
                resources = parseProtobufMessages(paginated_response.results)
                logger.info(f"Generating {len(resources)} {asset_type}'s")
                yield resources
        except PermissionDenied as e:
            logger.error(
                f"Couldn't access the API to get kind {asset_type}: {str(e)}",
                kind=asset_type,
            )
        except Exception as e:
            logger.error(str(e), kind=asset_type)
        return

    async def create_feed(self, feed: CloudAssetInventoryFeed) -> None:
        create_feed_request = {
            "feed_id": feed.id,
            "parent": self._parent,
            "feed": {
                "name": f"{self._parent}/feeds/{feed.id}",
                "asset_types": feed.asset_types,
                "content_type": RESOURCE_METADATA_CONTENT_TYPE,
                "condition": {
                    "expression": f'"{self._parent}" in temporal_asset.asset.ancestors'
                },
                "feed_output_config": {
                    "pubsub_destination": {"topic": feed.topic_name}
                },
            },
        }

        await self.async_assets_client.create_feed(request=create_feed_request)

    async def _list_feeds(self) -> list[dict[Any, Any]]:
        request = ListFeedsRequest()
        request.parent = self._parent
        active_feeds = await self.async_assets_client.list_feeds(request=request)
        return parseProtobufMessages(active_feeds.feeds)

    async def create_assets_feed_if_not_exists(
        self, feed: CloudAssetInventoryFeed
    ) -> None:
        try:
            existing_feeds = await self._list_feeds()
            if feed.id in [
                existing_feed["name"].split("/")[-1] for existing_feed in existing_feeds
            ]:
                logger.debug(f"Assets Feed {feed.id} already exists, not creating..")
            else:
                logger.info(f"Creating assets feed {feed.id}")
                await self.create_feed(feed)
        except PermissionDenied:
            logger.warning(
                "Service account has no permissions to list/create feeds. Please refer to our docs to find and set the correct permissions."
            )
