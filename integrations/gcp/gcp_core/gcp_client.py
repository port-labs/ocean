from collections.abc import MutableSequence
from typing import Any, AsyncGenerator, Optional, TypeVar

import proto  # type: ignore
from google.api_core.exceptions import PermissionDenied
from google.cloud.asset_v1 import (
    AssetServiceAsyncClient,
    
    ContentType,
)
from google.cloud.asset_v1.services.asset_service import pagers
from loguru import logger

RESOURCE_METADATA_CONTENT_TYPE = ContentType(1)

T = TypeVar("T", bound=proto.Message)


def parse_protobuf_messages(messages: MutableSequence[T]) -> list[dict[str, Any]]:
    return [proto.Message.to_dict(message) for message in messages]


class GCPClient:
    def __init__(self, parent: str, service_account_file: str) -> None:
        self.async_assets_client: AssetServiceAsyncClient = (
            AssetServiceAsyncClient.from_service_account_file(service_account_file)
        )
        self.async_pubsub_client: AssetServiceAsyncClient = (
            AssetServiceAsyncClient.from_service_account_file(service_account_file)
        )
        self._parent = parent

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
                resources = parse_protobuf_messages(paginated_response.results)
                logger.info(f"Generating {len(resources)} {asset_type}'s")
                yield resources
        except PermissionDenied as e:
            logger.error(f"Couldn't access the API to get kind {asset_type}: {str(e)}")
        except Exception as e:
            logger.error(str(e))
        return