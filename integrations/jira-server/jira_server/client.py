from enum import StrEnum
from typing import Any, AsyncGenerator
import httpx
from loguru import logger
from port_ocean.utils import http_async_client


class ResourceKey(StrEnum):
    PROJECTS = "projects"
    ISSUES = "issues"


class JiraServerClient:
    def __init__(
        self,
        server_url: str,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.server_url = server_url
        self.api_url = f"{self.server_url}/rest/api/2"
        self.client = http_async_client

        if token is not None:
            self.client.headers.update({"Authorization": f"Bearer {token}"})
        elif username is not None and password is not None:
            self.client.auth = httpx.BasicAuth(username, password)
        else:
            raise ValueError(
                "Either token or both username and password must be provided"
            )

    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self.client.request(
            method=method, url=url, params=params, json=json, headers=headers
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _generate_base_req_params(startAt: int = 0) -> dict[str, Any]:
        return {"startAt": startAt}

    async def _get_paginated_data(
        self,
        url: str,
        extract_key: str | None = None,
        initial_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = initial_params or {}
        params |= self._generate_base_req_params()

        start_at = 0
        while True:
            params["startAt"] = start_at
            response_data = await self._send_api_request("GET", url, params=params)
            items = response_data.get(extract_key, []) if extract_key else response_data

            if not items:
                break

            yield items

            start_at += len(items)
            if "total" in response_data and start_at >= response_data["total"]:
                break

    # Single item lookups
    async def get_single_project(self, project_key: str) -> dict[str, Any]:
        """Get a single project by its key."""
        response = await self.client.get(f"{self.api_url}/project/{project_key}")
        response.raise_for_status()
        return response.json()

    async def get_single_issue(self, issue_key: str) -> dict[str, Any]:
        """Get a single issue by its key."""
        response = await self.client.get(f"{self.api_url}/issue/{issue_key}")
        response.raise_for_status()
        return response.json()

    async def get_single_user(self, username: str) -> dict[str, Any]:
        """
        Get a single user from Jira Server by username.
        Jira Server's API requires the legacy 'username' parameter.
        """
        response = await self.client.get(
            f"{self.api_url}/user", params={"username": username}
        )
        response.raise_for_status()
        return response.json()

    # Projects API currently doesn't support pagination
    async def get_all_projects(self) -> list[dict[str, Any]]:
        """Get all visible projects from Jira Server (no pagination)."""
        logger.info("Getting all projects from Jira Server")
        return await self._send_api_request("GET", f"{self.api_url}/project")

    async def get_paginated_issues(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get issues from Jira Server with pagination using the search endpoint."""
        logger.info("Getting issues from Jira Server (paginated)")
        params = params or {}
        if "jql" in params:
            logger.info(f"Using JQL filter: {params['jql']}")
        async for issues in self._get_paginated_data(
            f"{self.api_url}/search", "issues", initial_params=params
        ):
            yield issues

    async def get_paginated_users(
        self, username: str | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get users from Jira Server with pagination.
        The API endpoint is `/user/search` and accepts a 'username' query parameter.
        """
        if not username:
            # This is a workaround for Jira Server's API to get all users
            username = "''"
        logger.info("Getting users from Jira Server (paginated)")
        initial_params = {"username": username}
        async for users in self._get_paginated_data(
            f"{self.api_url}/user/search", None, initial_params
        ):
            yield users
