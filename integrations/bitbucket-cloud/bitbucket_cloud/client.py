from typing import Any, AsyncGenerator, Optional, List, Dict
import asyncio
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter
from loguru import logger
from bitbucket_cloud.helpers.exceptions import MissingIntegrationCredentialException
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean
from bitbucket_cloud.base_client import BitbucketBaseClient
from bitbucket_cloud.base_rotating_client import BaseRotatingClient
import time
from httpx import HTTPStatusError

PULL_REQUEST_STATE = "OPEN"
PULL_REQUEST_PAGE_SIZE = 50
PAGE_SIZE = 100


class BitbucketClient(BaseRotatingClient):
    """Client for interacting with Bitbucket Cloud API v2.0."""

    def __init__(self, base_client: BitbucketBaseClient, client_id: Optional[str] = None):
        super().__init__(base_client)
        self.base_url = self.base_client.base_url
        self.workspace = self.base_client.workspace
        self.client_id = client_id or f"client_{id(self)}"

    @classmethod
    def create_from_ocean_config(cls) -> "BitbucketClient":
        """Create a BitbucketClient from the Ocean config."""
        base_client = BitbucketBaseClient.create_from_ocean_config()
        return cls(base_client)

    async def _send_paginated_api_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        data_key: str = "values",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Handle paginated requests to Bitbucket API."""
        if params is None:
            params = {
                "pagelen": PAGE_SIZE,
            }
        while True:
            try:
                await self._ensure_client_available()
                limiter_id = id(self.current_limiter) if self.current_limiter else None
                logger.debug(f"Using client {self.client_id} with limiter {limiter_id} for API call to {url}")
                if self.current_limiter:
                    async with self.current_limiter:
                        response = await self.base_client.send_api_request(
                            method=method,
                            url=url,
                            params=params,
                        )
                else:
                    response = await self.base_client.send_api_request(
                        method=method,
                        url=url,
                        params=params,
                    )
                
                if values := response.get(data_key, []):
                    yield values
                url = response.get("next")
                if not url:
                    break

            except HTTPStatusError as e:
                if hasattr(e, "response") and e.response.status_code != 429:
                    raise
                logger.warning(f"Rate limit exceeded for client {self.client_id}, rotating to next client")
                await self._rotate_base_client()
                continue
            except Exception as e:
                logger.error(f"Error fetching data from {url}: {str(e)}")
                raise

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

    async def _get_pull_requests(
        self, repo_slug: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get pull requests for a repository."""
        params = {
            "state": PULL_REQUEST_STATE,
            "pagelen": PULL_REQUEST_PAGE_SIZE,
        }
        logger.info(
            f"Fetching pull requests for repository {repo_slug} in workspace {self.workspace}"
        )
        async for pull_requests in self._send_paginated_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/pullrequests",
            params=params,
        ):
            logger.info(
                f"Fetched batch of {len(pull_requests)} pull requests from repository {repo_slug} in workspace {self.workspace}"
            )
            yield pull_requests
        logger.info(
            f"Finished fetching pull requests for repository {repo_slug} in workspace {self.workspace}"
        )

    async def get_pull_requests(self):
        async for repositories in self.get_repositories():
            tasks = [
                self._get_pull_requests(repo.get("slug", repo["name"].lower()))
                for repo in repositories
            ]
            logger.info(f"Resyncing pull requests for {len(tasks)} repositories")
            async for batch in stream_async_iterators_tasks(*tasks):
                yield batch

    async def get_pull_request(
        self, repo_slug: str, pull_request_id: str
    ) -> dict[str, Any]:
        """Get a specific pull request by ID."""
        return await self.base_client.send_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/pullrequests/{pull_request_id}"
        )

    async def get_repository(self, repo_slug: str) -> dict[str, Any]:
        """Get a specific repository by slug."""
        return await self.base_client.send_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}"
        )
