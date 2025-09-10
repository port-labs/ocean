import base64
from typing import Any, AsyncIterator, Optional
from urllib.parse import quote

from loguru import logger

from gitlab.clients.base_client import HTTPBaseClient


class RestClient(HTTPBaseClient):
    DEFAULT_PAGE_SIZE = 100
    VALID_GROUP_RESOURCES = ["issues", "merge_requests", "labels", "search"]

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
                logger.info(
                    f"Received batch of {len(batch)} {resource_type} for project {project_path}"
                )
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
                logger.info(
                    f"Received batch of {len(batch)} {resource_type} for group {group_id}"
                )
                yield batch

    async def get_project_languages(
        self, project_path: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        encoded_project_path = quote(project_path, safe="")
        path = f"projects/{encoded_project_path}/languages"
        return await self.send_api_request("GET", path, params=params or {})

    async def get_file_data(
        self, project_id: str, file_path: str, ref: str
    ) -> dict[str, Any]:
        encoded_project_id = quote(project_id, safe="")
        encoded_file_path = quote(file_path, safe="")
        path = f"projects/{encoded_project_id}/repository/files/{encoded_file_path}"
        params = {"ref": ref}

        response = await self.send_api_request("GET", path, params=params)
        if response:
            response["content"] = base64.b64decode(response["content"]).decode("utf-8")
        return response

    async def get_file_content(
        self, project_id: str, file_path: str, ref: str
    ) -> Optional[str]:
        encoded_project_id = quote(project_id, safe="")
        encoded_file_path = quote(file_path, safe="")
        path = f"projects/{encoded_project_id}/repository/files/{encoded_file_path}"
        params = {"ref": ref}

        response = await self.send_api_request("GET", path, params=params)
        if not response:
            return None

        return base64.b64decode(response["content"]).decode("utf-8")

    async def _make_paginated_request(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        page = 1
        params_dict: dict[str, Any] = params or {}
        if "per_page" not in params_dict:
            params_dict["per_page"] = page_size

        while True:
            request_params = {**params_dict, "page": page}
            logger.debug(f"Fetching page {page} from {path}")

            response = await self.send_api_request("GET", path, params=request_params)
            # HTTP API returns a list directly, or empty dict for 404
            batch: list[dict[str, Any]] = response if isinstance(response, list) else []

            if not batch:
                break

            yield batch

            if len(batch) < page_size:
                logger.debug(f"Last page reached for {path}, no more data.")
                break

            page += 1
