from typing import Any, AsyncGenerator, Optional
from httpx import HTTPStatusError, Timeout
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
import base64


PAGE_SIZE = 100
CLIENT_TIMEOUT = 30


class BitbucketClient:
    """Client for interacting with Bitbucket Cloud API v2.0."""

    def __init__(
        self,
        workspace: str,
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        workspace_token: Optional[str] = None,
    ) -> None:
        self.base_url = "https://api.bitbucket.org/2.0"
        self.workspace = workspace
        self.client = http_async_client
        self.client.timeout = Timeout(30.0)

        if workspace_token:
            self.headers = {
                "Authorization": f"Bearer {workspace_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        elif app_password and username:
            self.credentials = f"{username}:{app_password}"
            self.encoded_credentials = base64.b64encode(
                self.credentials.encode()
            ).decode()
            self.headers = {
                "Authorization": f"Basic {self.encoded_credentials}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        else:
            raise ValueError(
                "Either workspace_token or both username and app_password must be provided"
            )

        self.client.headers.update(self.headers)

    async def _send_api_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        """Send request to Bitbucket API with error handling."""
        url = f"{self.base_url}/{endpoint}"
        response = await self.client.request(
            method=method, url=url, params=params, json=json_data
        )
        try:
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            error_data = e.response.json()
            error_message = error_data.get("error", {}).get("message", str(e))
            raise HTTPStatusError(error_message, request=e.request, response=e.response)

    async def _send_paginated_api_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Handle Bitbucket's pagination for API requests."""
        if params is None:
            params = {}

        while True:
            response = await self._send_api_request(
                endpoint, params=params, method=method
            )
            values = response.get("values", [])
            if values:
                yield values
            next_page = response.get("next")
            if not next_page:
                break
            endpoint = next_page.replace(self.base_url + "/", "")

    # Project endpoints
    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all projects in the workspace."""
        async for projects in self._send_paginated_api_request(
            f"workspaces/{self.workspace}/projects"
        ):
            yield projects

    # Repository endpoints
    @cache_iterator_result()
    async def get_repositories(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all repositories in the workspace."""
        async for repos in self._send_paginated_api_request(
            f"repositories/{self.workspace}"
        ):
            yield repos

    async def get_directory_contents(
        self, repo_slug: str, commit: str, path: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get contents of a directory."""
        async for contents in self._send_paginated_api_request(
            f"repositories/{self.workspace}/{repo_slug}/src/{commit}/{path}"
        ):
            yield contents

    # Pull request endpoints
    async def get_pull_requests(
        self, repo_slug: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get pull requests for a repository."""
        async for prs in self._send_paginated_api_request(
            f"repositories/{self.workspace}/{repo_slug}/pullrequests"
        ):
            yield prs
