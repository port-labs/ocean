from typing import Any, AsyncIterator, Optional
from urllib.parse import quote

from loguru import logger

from .base_client import HTTPBaseClient


class RestClient(HTTPBaseClient):
    DEFAULT_PAGE_SIZE = 100
    VALID_GROUP_RESOURCES = ["issues", "merge_requests", "labels"]

    async def get_paginated_resource(
        self, resource_type: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a paginated resource (e.g., projects, groups)."""
        async for batch in self._make_paginated_request(resource_type, params=params):
            yield batch

    async def get_paginated_project_resource(
        self,
        project_path: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a paginated project resource (e.g., labels)."""
        encoded_project_path = quote(project_path, safe="")
        path = f"projects/{encoded_project_path}/{resource_type}"
        async for batch in self._make_paginated_request(path, params=params):
            if batch:
                yield batch

    async def get_paginated_group_resource(
        self,
        group_id: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a paginated group resource (e.g., issues)."""
        path = f"groups/{group_id}/{resource_type}"
        async for batch in self._make_paginated_request(path, params=params):
            if batch:
                yield batch

    async def get_project_languages(
        self, project_path: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        encoded_project_path = quote(project_path, safe="")
        path = f"projects/{encoded_project_path}/languages"
        return await self.send_api_request("GET", path, params=params or {})

    async def _make_paginated_request(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        page = 1
        params_dict: dict[str, Any] = params or {}

        while True:
            request_params = {**params_dict, "per_page": page_size, "page": page}
            logger.debug(f"Fetching page {page} from {path}")

            response = await self.send_api_request("GET", path, params=request_params)
            
            if not response:
                break
            
            yield response

            if len(batch) < page_size:
                logger.debug(f"Last page reached for {path}, no more data.")
                break

            page += 1
