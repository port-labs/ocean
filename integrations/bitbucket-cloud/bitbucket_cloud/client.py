from typing import Any, AsyncGenerator, Optional
from httpx import HTTPError, HTTPStatusError
from loguru import logger
from port_ocean.utils import http_async_client
from bitbucket_cloud.helpers.exceptions import MissingIntegrationCredentialException
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter
from bitbucket_cloud.helpers.utils import BitbucketRateLimiterConfig
import base64

PULL_REQUEST_STATE = "OPEN"
PULL_REQUEST_PAGE_SIZE = 50
PAGE_SIZE = 100
RATE_LIMITER: RollingWindowLimiter = RollingWindowLimiter(
    limit=BitbucketRateLimiterConfig.LIMIT, window=BitbucketRateLimiterConfig.WINDOW
)


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
        return cls(
            workspace=ocean.integration_config["bitbucket_workspace"],
            host=ocean.integration_config["bitbucket_host_url"],
            username=ocean.integration_config.get("bitbucket_username"),
            app_password=ocean.integration_config.get("bitbucket_app_password"),
            workspace_token=ocean.integration_config.get("bitbucket_workspace_token"),
        )

    async def _send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
        return_full_response: bool = False,
    ) -> Any:
        """Send request to Bitbucket API with error handling."""
        response = await self.client.request(
            method=method, url=url, params=params, json=json_data
        )
        try:
            response.raise_for_status()
            return response if return_full_response else response.json()
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Requested resource not found: {url}; message: {str(e)}"
                )
                return {}
            logger.error(f"Bitbucket API error: {str(e)}")
            raise e
        except HTTPError as e:
            logger.error(f"Failed to send {method} request to url {url}: {str(e)}")
            raise e

    async def _fetch_paginated_api_with_rate_limiter(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
        data_key: str = "values",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Handle rate-limited paginated requests to Bitbucket API"""
        if params is None:
            params = {
                "pagelen": PAGE_SIZE,
            }
        while True:
            async with RATE_LIMITER:
                response = await self._send_api_request(
                    url, params=params, method=method
                )
                if values := response.get(data_key, []):
                    yield values
                url = response.get("next")
                if not url:
                    break

    async def _send_paginated_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
        data_key: str = "values",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Handle Bitbucket's pagination for API requests with a flexible data key.
        Args:
            url: The API endpoint to request.
            params: Optional dictionary of query parameters.
            method: The HTTP method to use.
            data_key: The key to use when extracting data from the API response.
        Yields:
            Lists of dictionaries containing the paginated data.
        """
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
        async for repos in self._fetch_paginated_api_with_rate_limiter(
            f"{self.base_url}/repositories/{self.workspace}", params=params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from workspace {self.workspace}"
            )
            yield repos

    async def get_directory_contents(
        self,
        repo_slug: str,
        branch: str,
        path: str,
        max_depth: int,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get contents of a directory."""
        if params is None:
            params = {
                "max_depth": max_depth,
                "pagelen": PAGE_SIZE,
            }
        async for contents in self._fetch_paginated_api_with_rate_limiter(
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
        async for pull_requests in self._fetch_paginated_api_with_rate_limiter(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/pullrequests",
            params=params,
        ):
            logger.info(
                f"Fetched batch of {len(pull_requests)} pull requests from repository {repo_slug} in workspace {self.workspace}"
            )
            yield pull_requests

    async def get_pull_request(
        self, repo_slug: str, pull_request_id: str
    ) -> dict[str, Any]:
        """Get a specific pull request by ID."""
        return await self._send_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/pullrequests/{pull_request_id}"
        )

    async def get_repository(self, repo_slug: str) -> dict[str, Any]:
        """Get a specific repository by slug."""
        return await self._send_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}"
        )

    async def get_repository_files(self, repo: str, branch: str, path: str) -> Any:
        """Get the content of a file."""
        response = await self._send_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo}/src/{branch}/{path}",
            method="GET",
            return_full_response=True,
        )
        logger.info(f"Retrieved file content for {repo}/{branch}/{path}")
        return response.text

    async def search_files(
        self,
        search_query: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Search for files using Bitbucket's search API."""
        params = {
            "pagelen": 300,
            "search_query": search_query,
            "fields": "+values.file.commit.repository.mainbranch.name",
        }

        async for results in self._send_paginated_api_request(
            f"{self.base_url}/workspaces/{self.workspace}/search/code",
            params=params,
        ):
            logger.info(
                f"Fetched batch of {len(results)} matching files from workspace {self.workspace}"
            )
            yield results
