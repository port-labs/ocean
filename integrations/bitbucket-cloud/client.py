from enum import StrEnum
from typing import Any, AsyncGenerator, Optional
from httpx import HTTPStatusError
from loguru import logger
from port_ocean.utils import http_async_client
from helpers.exceptions import MissingIntegrationCredentialException
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean
import base64

PAGE_SIZE = 100


class ObjectKind(StrEnum):
    PROJECT = "project"
    FOLDER = "folder"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"


class BitbucketClient:
    """Client for interacting with Bitbucket Cloud API v2.0."""

    def __init__(
        self,
        workspace: str,
        host: str,
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        workspace_token: Optional[str] = None,
    ) -> None:
        self.base_url = host
        self.workspace = workspace
        self.client = http_async_client

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
            raise MissingIntegrationCredentialException(
                "Either workspace_token or both username and app_password must be provided"
            )
        self.client.headers.update(self.headers)

    @classmethod
    def create_from_ocean_config(cls) -> "BitbucketClient":
        return cls(
            workspace=ocean.integration_config["bitbucket_workspace"],
            host=ocean.integration_config["bitbucket_host_url"],
            username=ocean.integration_config.get("bitbucket_username"),
            app_password=ocean.integration_config.get("bitbucket_app_password"),
            workspace_token=ocean.integration_config.get("bitbucket_workspace_token"),
        )

    async def _send_api_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        url: Optional[str] = None,
        method: str = "GET",
    ) -> Any:
        """Send request to Bitbucket API with error handling."""
        url = url or f"{self.base_url}/{endpoint}"
        response = await self.client.request(
            method=method, url=url, params=params, json=json_data
        )
        try:
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            error_data = e.response.json()
            error_message = error_data.get("error", {}).get("message", str(e))
            if e.response.status_code == 404:
                logger.error(
                    f"Requested resource not found: {url}; message: {error_message}"
                )
                return {}
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
        next_page = None

        while True:
            response = await self._send_api_request(
                endpoint, params=params, method=method, url=next_page
            )
            if values := response.get("values", []):
                yield values
            next_page = response.get("next")
            if not next_page:
                break

    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all projects in the workspace."""
        async for projects in self._send_paginated_api_request(
            f"workspaces/{self.workspace}/projects"
        ):
            yield projects

    @cache_iterator_result()
    async def get_repositories(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all repositories in the workspace."""
        async for repos in self._send_paginated_api_request(
            f"repositories/{self.workspace}", params=params
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
