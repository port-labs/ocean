from enum import StrEnum
from typing import Any, AsyncGenerator
import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from jira_server.helpers.utils import IgnoredError

PAGE_SIZE = 100


IGNORED_ERRORS = [
    IgnoredError(status=404, message="Resource not found"),
]


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

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        url: str,
        method: str,
        ignored_errors: list[IgnoredError] | None = None,
    ) -> bool:
        """Check if an HTTP error should be ignored based on the ignored_errors list."""
        if not ignored_errors:
            return False

        status_code = error.response.status_code

        for ignored_error in ignored_errors:
            if str(status_code) == str(ignored_error.status):
                logger.warning(
                    f"Ignored error {status_code} for {method} {url}: "
                    f"{ignored_error.message or 'No message'}"
                )
                return True
        return False

    def _log_jira_error_response(
        self,
        response: httpx.Response,
        method: str,
        url: str,
    ) -> None:
        """Log descriptive error messages from Jira API responses."""
        try:
            error_body = response.json()
            logger.error(
                f"Jira API request failed with (HTTP {response.status_code}) for {method} {url} . "
                f"See response for details: {error_body}"
            )
        except Exception:
            logger.error(
                f"Jira API request failed with (HTTP {response.status_code}) for {method} {url} . "
                f"See response for details: {response.text}"
            )

    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        ignored_errors: list[IgnoredError] | None = None,
    ) -> Any:
        """Send an API request with optional error ignoring.

        Returns an empty dict {} for ignored errors, allowing callers to handle gracefully.
        """
        try:
            response = await self.client.request(
                method=method, url=url, params=params, json=json, headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if self._should_ignore_error(e, url, method, ignored_errors):
                return {}
            self._log_jira_error_response(e.response, method, url)
            raise

    @staticmethod
    def _generate_base_req_params(startAt: int = 0) -> dict[str, Any]:
        return {"startAt": startAt}

    async def _get_paginated_data(
        self,
        url: str,
        extract_key: str | None = None,
        initial_params: dict[str, Any] | None = None,
        ignored_errors: list[IgnoredError] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = initial_params or {}
        params |= self._generate_base_req_params()

        start_at = 0
        while True:
            params["startAt"] = start_at
            response_data = await self._send_api_request(
                "GET", url, params=params, ignored_errors=ignored_errors
            )

            if not response_data:
                logger.info(
                    "Stopping pagination due to empty response or ignored error"
                )
                break

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
            f"{self.api_url}/search",
            "issues",
            initial_params=params,
            ignored_errors=IGNORED_ERRORS,
        ):
            yield issues

    async def _get_cursor_paginated_data(
        self, url: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Generic cursor-based pagination handler for Jira REST APIs that return:
        {
          "values": [...],
          "nextCursor": "<string>",
          "isLast": true/false
        }
        """
        params = params or {}
        cursor = None

        while True:
            effective_params = {**params}
            if cursor:
                effective_params["cursor"] = cursor

            response = await self._send_api_request("GET", url, params=effective_params)
            values = response["values"]
            if not values:
                break

            yield values

            cursor = response.get("nextCursor")
            if not cursor or response["isLast"]:
                break

    async def get_paginated_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get all users from Jira Server or Data Center.
        - Tries /user/list (cursor-based, Jira ≥ 10)
        - Falls back to /user/search (legacy, Jira < 10)
        """
        try:
            async for users in self._fetch_users_via_list():
                logger.info(
                    f"Successfully fetched batch of {len(users)} users via /user/list"
                )
                yield users

            return
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("/user/list unsupported, falling back to /user/search")
            else:
                raise

        async for users in self._fetch_users_via_search():
            logger.info(
                f"Fetched batch of {len(users)} users via /user/search fallback"
            )
            yield users

    async def _fetch_users_via_search(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch users using the legacy /user/search endpoint (Jira < 10)."""
        url = f"{self.api_url}/user/search"
        # This is a workaround for Jira Server's API to get all users
        params = {"username": "''", "maxResults": PAGE_SIZE}

        logger.debug("Fetching users via /user/search")
        async for users in self._get_paginated_data(url=url, initial_params=params):
            yield users

    async def _fetch_users_via_list(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch users using the modern /user/list endpoint (Jira ≥ 10)."""
        url = f"{self.api_url}/user/list"
        params = {"maxResults": PAGE_SIZE}

        logger.debug("Fetching users via /user/list (cursor-based pagination)")
        async for users in self._get_cursor_paginated_data(url, params):
            yield users
