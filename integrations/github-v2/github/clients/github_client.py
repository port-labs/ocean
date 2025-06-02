import asyncio
from functools import partial
from typing import Any, AsyncIterator, Optional

from loguru import logger
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from port_ocean.utils.cache import cache_iterator_result

from github.clients.rest_client import RestClient
from github.helpers.rate_limiter import BasicGitHubRateLimiter


class GitHubClient:
    DEFAULT_PARAMS = {
        "sort": "updated",
        "direction": "desc",
    }

    def __init__(self, base_url: str, token: str) -> None:
        self.rate_limiter = BasicGitHubRateLimiter()
        self.rest = RestClient(base_url, token, github_client=self)
        # Note: Removed set_github_client call as rate limiting has been removed

    @cache_iterator_result()
    async def get_repositories(
        self,
        params: Optional[dict[str, Any]] = None,
        max_concurrent: int = 10,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch repositories accessible to the authenticated user."""
        request_params = self.DEFAULT_PARAMS | (params or {})
        async for repos_batch in self.rest.get_paginated_resource(
            "user/repos", params=request_params
        ):
            logger.info(f"Received batch with {len(repos_batch)} repositories")
            yield repos_batch

    @cache_iterator_result()
    async def get_organizations(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch organizations for the authenticated user."""
        async for batch in self.rest.get_paginated_resource("user/orgs", params=params):
            yield batch

    async def get_repositories_resource(
        self,
        repos_batch: list[dict[str, Any]],
        resource_type: str,
        max_concurrent: int = 10,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a resource for each repository in the batch."""
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            semaphore_async_iterator(
                semaphore,
                partial(
                    self.rest.get_paginated_repo_resource,
                    repo["owner"]["login"],
                    repo["name"],
                    resource_type,
                    params,
                ),
            )
            for repo in repos_batch
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            if batch:
                yield batch

    async def get_organizations_resource(
        self,
        orgs_batch: list[dict[str, Any]],
        resource_type: str,
        max_concurrent: int = 10,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a resource for each organization in the batch."""
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            semaphore_async_iterator(
                semaphore,
                partial(
                    self.rest.get_paginated_org_resource,
                    org["login"],
                    resource_type,
                    params,
                ),
            )
            for org in orgs_batch
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            if batch:
                yield batch

    async def fetch_rate_limit_from_endpoint(self) -> dict[str, Any]:
        """
        Fetches the current rate limit status directly from GitHub's /rate_limit endpoint.
        """
        try:
            logger.debug("GitHubClient fetching /rate_limit endpoint.")
            # Use the underlying rest client to make the call, bypassing its own rate limiting for this specific call
            # to avoid circular dependencies if the rate limiter itself needs to make this call.
            # This means send_api_request in RestClient needs a way to bypass the limiter for this specific path.
            # For now, let's assume send_api_request can handle it or we add a specific method in RestClient.
            response = await self.rest.send_api_request(
                "GET", "rate_limit", bypass_rate_limiter=True
            )
            return response.get(
                "resources", {}
            )  # The actual data is nested under "resources"
        except Exception as e:
            logger.error(f"Failed to fetch rate limit from GitHub endpoint: {e}")
            return {}  # Return empty on failure to avoid breaking the limiter logic
