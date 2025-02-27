from typing import Optional, AsyncIterator, Any, Dict, Callable
from loguru import logger
from .auth_client import AuthClient
from port_ocean.utils import http_async_client


class RestClient:
    def __init__(self, base_url: str, auth_client: AuthClient):
        self.base_url = f"{base_url}/api/v4"
        self.auth_client = auth_client
        self._client = http_async_client

    async def send_api_request(
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
                headers=self.auth_client.get_headers(),
                params=params,
                json=data,
            )

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to make {method} request to {path}: {str(e)}")
            raise

    async def make_paginated_request(
        self, path: str, params: Optional[dict[str, Any]] = None, page_size: int = 100
    ) -> AsyncIterator[list[dict[str, Any]]]:
        page = 1
        params = params or {}

        while True:
            request_params = {**params, "per_page": page_size, "page": page}
            logger.debug(f"Fetching page {page} from {path}")

            response = await self.send_api_request("GET", path, params=request_params)

            if not response:
                logger.debug(f"No more records to fetch for {path}.")
                break

            yield response

            if len(response) < page_size:
                logger.debug(f"Last page reached for {path}, no more data.")
                break

            page += 1

    async def get_group_resource(
        self, group_id: str, resource_type: str, params: Optional[dict] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        if resource_type not in ["issues", "merge_requests"]:
            raise ValueError(f"Unsupported resource type: {resource_type}")

        path = f"groups/{group_id}/{resource_type}"
        default_params = {"state": "all"}
        merged_params = {**default_params, **(params or {})}

        try:
            async for batch in self.make_paginated_request(
                path,
                params=merged_params,
                page_size=100,
            ):
                if batch:
                    yield batch
        except Exception as e:
            logger.error(
                f"Failed to fetch {resource_type} for group {group_id}: {str(e)}"
            )
            raise
