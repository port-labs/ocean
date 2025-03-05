from typing import Any, AsyncIterator, Optional

from loguru import logger
from port_ocean.utils import http_async_client

from .auth_client import AuthClient


class RestClient:
    DEFAULT_PAGE_SIZE = 100
    VALID_GROUP_RESOURCES = ["issues", "merge_requests", "labels"]

    # Define resource-specific default parameters
    RESOURCE_PARAMS = {
        "labels": {
            "with_counts": True,
            "include_descendant_groups": True,
            "only_group_labels": False,
        },
        "issues": {"state": "all"},
        "merge_requests": {"state": "all"},
    }

    def __init__(self, base_url: str, auth_client: AuthClient):
        self.base_url = f"{base_url}/api/v4"
        self._headers = auth_client.get_headers()
        self._client = http_async_client

    async def get_resource(
        self, resource_type: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        try:
            async for batch in self._make_paginated_request(
                resource_type, params=params
            ):
                yield batch
        except Exception as e:
            logger.error(f"Failed to fetch {resource_type}: {str(e)}")
            raise

    async def get_group_resource(
        self, group_id: str, resource_type: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        if resource_type not in self.VALID_GROUP_RESOURCES:
            raise ValueError(f"Unsupported resource type: {resource_type}")

        path = f"groups/{group_id}/{resource_type}"

        # Get default params for the resource type
        default_params = self.RESOURCE_PARAMS.get(resource_type, {})
        merged_params = {**default_params, **(params or {})}

        try:
            async for batch in self._make_paginated_request(
                path,
                params=merged_params,
                page_size=self.DEFAULT_PAGE_SIZE,
            ):
                if batch:
                    yield batch
        except Exception as e:
            logger.error(
                f"Failed to fetch {resource_type} for group {group_id}: {str(e)}"
            )
            raise

    async def _make_paginated_request(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        page = 1
        params = params or {}

        while True:
            request_params = {**params, "per_page": page_size, "page": page}
            logger.debug(f"Fetching page {page} from {path}")

            response = await self._send_api_request("GET", path, params=request_params)

            if not response:
                logger.debug(f"No more records to fetch for {path}.")
                break

            yield response

            if len(response) < page_size:
                logger.debug(f"Last page reached for {path}, no more data.")
                break

            page += 1

    async def _send_api_request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        try:
            url = f"{self.base_url}/{path}"
            logger.debug(f"Sending {method} request to {url}")

            response = await self._client.request(
                method=method,
                url=url,
                headers=self._headers,
                params=params,
                json=data,
            )

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to make {method} request to {path}: {str(e)}")
            raise
