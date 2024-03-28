from typing import Any, AsyncGenerator
from gcp_core.utils import parseProtobufMessages
from google.cloud.asset_v1 import (
    AssetServiceAsyncClient,
    ListAssetsRequest,
    ContentType,
)
from google.api_core.exceptions import PermissionDenied
from loguru import logger
from google.cloud.asset_v1.services.asset_service import pagers

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean


class GCPClient:
    def __init__(self, organization_id: str, service_account_file: str) -> None:
        self._organization = organization_id
        self._asset_client: AssetServiceAsyncClient = (
            AssetServiceAsyncClient.from_service_account_file(service_account_file)
        ) #TODO: Use another method of authentication

    @classmethod
    def create_from_ocean_config(cls) -> "GCPClient":
        if cache := event.attributes.get("gcp_client"):
            return cache
        gcp_client = cls(
            ocean.integration_config["organization_id"],
            ocean.integration_config["service_account_file_location"],
        )
        event.attributes["gcp_client"] = gcp_client
        return gcp_client
    

    async def generate_assets(
        self, asset_name: str
    ) -> AsyncGenerator[list[dict[Any, Any]], Any]:
        try:
            list_assets_request = self._generateListRequest(asset_name)
            paginated_responses: pagers.ListAssetsAsyncPager = (
                await self._asset_client.list_assets(list_assets_request)
            )
            async for paginated_response in paginated_responses.pages:
                yield parseProtobufMessages(paginated_response.assets)
        except PermissionDenied as e:
            logger.error(
                f"Couldn't access the API to get kind {asset_name}: {str(e)}",
                kind=asset_name,
            )
        except Exception as e:
            logger.error(str(e), kind=asset_name)
        return

    def _generateListRequest(self, asset_name: str) -> ListAssetsRequest:
        request = ListAssetsRequest()
        request.asset_types = [asset_name]
        # request.parent=f'organizations/{organization_id}' # TODO: Enable at org level
        request.parent = f"projects/{self._organization}"
        request.content_type = ContentType(1)
        return request
