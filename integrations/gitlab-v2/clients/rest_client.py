from typing import Any, AsyncIterator, Optional
from loguru import logger
from .base_client import HTTPBaseClient
from urllib.parse import quote


class RestClient(HTTPBaseClient):
    DEFAULT_PAGE_SIZE = 100
    VALID_GROUP_RESOURCES = ["issues", "merge_requests", "labels"]

    RESOURCE_PARAMS = {
        "labels": {
            "with_counts": True,
            "include_descendant_groups": True,
            "only_group_labels": False,
        }
    }

    async def get_resource(
        self, resource_type: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a paginated resource (e.g., projects, groups)."""
        async for batch in self._make_paginated_request(resource_type, params=params):
            yield batch

    async def get_project_resource(
        self,
        project_path: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a paginated project resource (e.g., labels)."""
        encoded_project_path = quote(project_path, safe='')
        path = f"projects/{encoded_project_path}/{resource_type}"
        async for batch in self._make_paginated_request(path, params=params):
            if batch:
                yield batch

    async def get_group_resource(
        self, group_id: str, resource_type: str
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a paginated group resource (e.g., labels)."""
        if resource_type not in self.VALID_GROUP_RESOURCES:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        path = f"groups/{group_id}/{resource_type}"
        request_params = self.RESOURCE_PARAMS.get(resource_type, {})
        async for batch in self._make_paginated_request(path, params=request_params):
            if batch:
                yield batch

    async def get_project_languages(
        self, project_path: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        encoded_project_path = quote(project_path, safe='')
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

            # REST API returns a list directly, or empty dict for 404
            batch: list[dict[str, Any]] = response if isinstance(response, list) else []

            if not batch:
                logger.debug(f"No more records to fetch for {path}.")
                break

            yield batch

            if len(batch) < page_size:
                logger.debug(f"Last page reached for {path}, no more data.")
                break

            page += 1
