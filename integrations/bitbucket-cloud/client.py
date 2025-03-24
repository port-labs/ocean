from typing import Any, AsyncGenerator, Optional
from httpx import HTTPError, HTTPStatusError
from loguru import logger
from port_ocean.utils import http_async_client
from helpers.exceptions import MissingIntegrationCredentialException
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean
import base64

PULL_REQUEST_STATE = "OPEN"
PULL_REQUEST_PAGE_SIZE = 50
PAGE_SIZE = 100


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
                "Either workspace token or both username and app password must be provided"
            )
        self.client.headers.update(self.headers)

    @classmethod
    def create_from_ocean_config(cls) -> "BitbucketClient":
        """Create a BitbucketClient from the Ocean config."""
        credentials = ocean.integration_config.get("bitbucket_credentials")
        if not credentials:
            raise MissingIntegrationCredentialException(
                "Either workspace token or both username and app password must be provided"
            )
        credentials = credentials.split(",")[0]
        username, app_password = (
            credentials.split("::") if "::" in credentials else (None, None)
        )
        if credentials and not username and not app_password:
            workspace_token = credentials
            return cls(
                workspace=ocean.integration_config["bitbucket_workspace"],
                host=ocean.integration_config["bitbucket_host_url"],
                workspace_token=workspace_token,
            )
        elif username and app_password:
            return cls(
                workspace=ocean.integration_config["bitbucket_workspace"],
                host=ocean.integration_config["bitbucket_host_url"],
                username=username,
                app_password=app_password,
            )
        else:
            raise MissingIntegrationCredentialException(
                "Either workspace token or both username and app password must be provided"
            )

    async def _send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        """Send request to Bitbucket API with error handling."""
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
        except HTTPError as e:
            logger.error(f"Failed to send {method} request to url {url}: {str(e)}")
            raise e

    async def _send_paginated_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
        data_key: str = "values",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Handle paginated requests to Bitbucket API."""
        if params is None:
            params = {
                "pagelen": PAGE_SIZE,
            }
        while True:
            response = await self._send_api_request(url, params=params, method=method)
            if values := response.get(data_key, []):
                yield values
            url = response.get("next")
            if not url:
                break

    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all projects in the workspace."""
        async for projects in self._send_paginated_api_request(
            f"{self.base_url}/workspaces/{self.workspace}/projects"
        ):
            logger.info(
                f"Fetched batch of {len(projects)} projects from workspace {self.workspace}"
            )
            yield projects

    @cache_iterator_result()
    async def get_repositories(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all repositories in the workspace."""
        async for repos in self._send_paginated_api_request(
            f"{self.base_url}/repositories/{self.workspace}", params=params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from workspace {self.workspace}"
            )
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
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/src/{branch}/{path}",
            params=params,
        ):
            logger.info(
                f"Fetched directory contents batch with {len(contents)} contents"
            )
            yield contents

    async def get_pull_requests(
        self, repo_slug: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get pull requests for a repository."""
        params = {
            "state": PULL_REQUEST_STATE,
            "pagelen": PULL_REQUEST_PAGE_SIZE,
        }
        async for pull_requests in self._send_paginated_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/pullrequests",
            params=params,
        ):
            logger.info(
                f"Fetched batch of {len(pull_requests)} pull requests from repository {repo_slug} in workspace {self.workspace}"
            )
            yield pull_requests
