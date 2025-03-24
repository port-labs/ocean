from typing import Any, AsyncIterator, Optional
from loguru import logger
from .base_client import HTTPBaseClient
import base64
import urllib.parse


class RestClient(HTTPBaseClient):
    DEFAULT_PAGE_SIZE = 100
    VALID_GROUP_RESOURCES = ["issues", "merge_requests", "labels", "search"]

    async def get_paginated_resource(
        self, resource_type: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
<<<<<<< HEAD
        try:
            async for batch in self._make_paginated_request(resource_type, params):
=======
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
        encoded_project_path = quote(project_path, safe="")
        path = f"projects/{encoded_project_path}/{resource_type}"
        async for batch in self._make_paginated_request(path, params=params):
            if batch:
>>>>>>> 894478946a18175517e98dc740f6c87d3407cb3b
                yield batch

    async def get_paginated_group_resource(
        self,
        group_id: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a paginated group resource (e.g., labels)."""
        if resource_type not in self.VALID_GROUP_RESOURCES:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        path = f"groups/{group_id}/{resource_type}"
        request_params = self.RESOURCE_PARAMS.get(resource_type, {})
        async for batch in self._make_paginated_request(path, params=request_params):
            if batch:
                yield batch

<<<<<<< HEAD
        if params:
            request_params.update(params)

        try:
            async for batch in self._make_paginated_request(
                path,
                params=request_params,
                page_size=self.DEFAULT_PAGE_SIZE,
            ):
                if batch:
                    yield batch
        except Exception as e:
            logger.error(
                f"Failed to fetch {resource_type} for group {group_id}: {str(e)}"
            )
            raise
=======
    async def get_project_languages(
        self, project_path: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        encoded_project_path = quote(project_path, safe="")
        path = f"projects/{encoded_project_path}/languages"
        return await self.send_api_request("GET", path, params=params or {})
>>>>>>> 894478946a18175517e98dc740f6c87d3407cb3b

    async def get_project_resource(
        self,
        project_path: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:

        path = f"projects/{project_path}/{resource_type}"

        request_params = params or {}

        try:
            async for batch in self._make_paginated_request(
                path,
                params=request_params,
                page_size=self.DEFAULT_PAGE_SIZE,
            ):
                if batch:
                    yield batch
        except Exception as e:
            logger.error(
                f"Failed to fetch {resource_type} for project {project_path}: {str(e)}"
            )
            raise

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

    async def get_file_content(
        self, project_id: str, file_path: str, ref: str = "main"
    ) -> Optional[str]:
        """
        Get the content of a file from a repository.

        Args:
            project_id: The ID or URL-encoded path of the project
            file_path: The path of the file inside the repository
            ref: The name of the branch, tag or commit

        Returns:
            The file content as a string if found, None otherwise
        """
        try:
            encoded_project_id = urllib.parse.quote(str(project_id), safe="")
            encoded_file_path = urllib.parse.quote(file_path, safe="")

            path = f"projects/{encoded_project_id}/repository/files/{encoded_file_path}"
            params = {"ref": ref}

            response = await self.send_api_request("GET", path, params=params)
            if not response:
                logger.warning(
                    f"No file content returned for {file_path} in project {project_id}"
                )
                return None

            content = response.get("content", "")
            if not content:
                return None

            try:
                return base64.b64decode(content).decode("utf-8")
            except Exception as e:
                logger.error(f"Failed to decode file content: {str(e)}")
                return None

        except Exception as e:
            logger.error(
                f"Failed to fetch file {file_path} from project {project_id}: {str(e)}"
            )
            return None
