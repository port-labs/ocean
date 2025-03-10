from typing import Any, AsyncGenerator, Optional
from httpx import HTTPStatusError, Timeout
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean
from aiolimiter import AsyncLimiter
import base64

PAGE_SIZE = 100
CLIENT_TIMEOUT = 30
MAX_RATE_LIMIT = 800
THROTTLE_PERIOD = 3600
REPOSITORY_ASYNC_LIMITER = AsyncLimiter(MAX_RATE_LIMIT, THROTTLE_PERIOD)


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
        self.client.timeout = Timeout(CLIENT_TIMEOUT)

        if workspace_token:
            self.headers = {
                "Authorization": f"Bearer {workspace_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        elif app_password and username:
            self.encoded_credentials = base64.b64encode(
                f"{username}:{app_password}".encode()
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

    @classmethod
    def create_from_ocean_config(cls) -> "BitbucketClient":
        return cls(
            workspace=ocean.integration_config["bitbucket_workspace"],
            username=ocean.integration_config.get("bitbucket_username"),
            app_password=ocean.integration_config.get("bitbucket_app_password"),
            workspace_token=ocean.integration_config.get("bitbucket_workspace_token"),
        )

    async def _send_api_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
        return_full_response: bool = False,
    ) -> Any:
        """Send request to Bitbucket API with error handling."""
        url = f"{self.base_url}/{endpoint}"
        if endpoint.startswith("repositories"):
            async with REPOSITORY_ASYNC_LIMITER:
                response = await self.client.request(
                    method=method, url=url, params=params, json=json_data
                )
        else:
            response = await self.client.request(
                method=method, url=url, params=params, json=json_data
            )
        try:
            response.raise_for_status()
            if return_full_response:
                return response
            return response.json()
        except HTTPStatusError as e:
            error_data = e.response.json()
            error_message = error_data.get("error", {}).get("message", str(e))
            logger.error(f"Bitbucket API error: {error_message}")
            raise e

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
            values = response["values"]
            if values:
                yield values
            next_page = response.get("next")
            if not next_page:
                break
            endpoint = next_page.replace(self.base_url + "/", "")

    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all projects in the workspace."""
        async for projects in self._send_paginated_api_request(
            f"workspaces/{self.workspace}/projects"
        ):
            yield projects

    @cache_iterator_result()
    async def get_repositories(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all repositories in the workspace."""
        async for repos in self._send_paginated_api_request(
            f"repositories/{self.workspace}"
        ):
            yield repos

    async def get_directory_contents(
        self, repo_slug: str, branch: str, path: str, max_depth: int = 2
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get contents of a directory."""
        params = {
            "max_depth": max_depth,
            "pagelen": PAGE_SIZE,
        }
        async for contents in self._send_paginated_api_request(
            f"repositories/{self.workspace}/{repo_slug}/src/{branch}/{path}",
            params=params,
        ):
            yield contents

    async def get_pull_requests(
        self, repo_slug: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get pull requests for a repository."""
        async for pull_requests in self._send_paginated_api_request(
            f"repositories/{self.workspace}/{repo_slug}/pullrequests"
        ):
            yield pull_requests

    async def get_pull_request(
        self, repo_slug: str, pull_request_id: str
    ) -> dict[str, Any]:
        """Get a specific pull request by ID."""
        return await self._send_api_request(
            f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pull_request_id}"
        )

    async def get_repository(self, repo_slug: str) -> dict[str, Any]:
        """Get a specific repository by slug."""
        return await self._send_api_request(
            f"repositories/{self.workspace}/{repo_slug}"
        )

    async def retrieve_diff_stat(
        self, repo: str, old_hash: str, new_hash: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve diff statistics between two commits using Bitbucket API
        """
        logger.debug(
            f"Retrieving diff stat for workspace: {self.workspace}, repo: {repo}, old_hash: {old_hash}, new_hash: {new_hash}; retrieve_diff_stat"
        )
        async for diff_stat in self._send_paginated_api_request(
            f"repositories/{self.workspace}/{repo}/diffstat/{new_hash}..{old_hash}",
            params={"pagelen": 500},
        ):
            yield diff_stat

    async def get_file_content(self, repo: str, branch: str, path: str) -> Any:
        """Get the content of a file."""
        response = await self._send_api_request(
            f"repositories/{self.workspace}/{repo}/src/{branch}/{path}",
            method="GET",
            return_full_response=True,
        )
        return response.text
