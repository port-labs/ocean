from typing import AsyncGenerator, Any, Optional

from httpx import HTTPError, HTTPStatusError
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from .auth import AuthClient
from .rate_limiter import (
    RollingWindowLimiter,
    GitHubRateLimiter,
)

# constants
DEFAULT_PAGE_SIZE = 100

# rate limiter
RATE_LIMITER: RollingWindowLimiter = RollingWindowLimiter(
    limit=GitHubRateLimiter.LIMIT,
    window=GitHubRateLimiter.WINDOW_TTL,
)


class IntegrationClient:
    def __init__(self, auth_client: AuthClient):
        logger.info("Initializing integration client")

        # configure base url
        self.base_url = ocean.integration_config["base_url"]

        # http client setup
        self._client = http_async_client
        self._auth_client = auth_client

        # configure headers for an http client
        self._client.headers.update(self._auth_client.get_headers())

    async def _send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
        values_key: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """Send a request to Bitbucket v2 API with error handling."""
        logger.info(f"Sending request to {url}")

        try:
            response = await self._client.request(
                method=method, url=url, params=params, json=json_data
            )
            response.raise_for_status()

            if values_key is None:
                data = response.json()
            else:
                data = response.json().get(values_key, [])

            # get response headers
            return data, dict(response.headers)

        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Requested resource not found: {url}; message: {str(e)}"
                )
                return [], {}
            logger.error(f"API error: {str(e)}")
            raise e

        except HTTPError as e:
            logger.error(f"Failed to send {method} request to url {url}: {str(e)}")
            raise e

    async def _fetch_data(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
        values_key: Optional[str] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """handles HTTP calls to the API server"""

        if params is None:
            params = {
                "per_page": DEFAULT_PAGE_SIZE,
                "page": 1,
                "sort": "asc",
            }

        while True:
            async with RATE_LIMITER:
                try:
                    response, headers = await self._send_api_request(
                        method=method, url=url, params=params, values_key=values_key
                    )
                    logger.info(f"Fetched {len(response)} items from {url}")
                    yield response

                    if headers is None:
                        # no headers available, break the loop
                        break

                    # get the `Link` header from the last response
                    link_header = headers.get("link")

                    if not link_header:
                        # no new pages
                        logger.info(f"Link header not found for {url}. Skipping")
                        break

                    for link in link_header.split(","):
                        parts = link.strip().split(";")
                        url = parts[0].strip("<>")
                        rel = parts[1].strip()
                        if 'rel="next"' in rel:
                            # update `url` and params for the next request
                            url = url
                            params = None
                            logger.info(f"Next page: {url}")
                            break
                    else:  # no break occurred - no next link found
                        logger.info(f"No more pages available from {url}")
                        break

                except BaseException as e:
                    logger.error(f"An error occurred while fetching {url}: {e}")
                    yield []
                    break

    @cache_iterator_result()
    async def get_repositories(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """get all repos for the current user"""
        async for repos in self._fetch_data(f"{self.base_url}/user/repos"):
            yield repos

    async def get_issues(
        self,
        repo_slug: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """get all issues for a repo"""
        params = {
            "per_page": DEFAULT_PAGE_SIZE,
            "page": 1,
            "sort": "updated",
        }
        async for issues in self._fetch_data(
            f"{self.base_url}/repos/{self._auth_client.get_user_agent()}/{repo_slug}/issues",
            params=params,
        ):
            yield issues

    async def get_workflows(
        self,
        repo_slug: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """get all workflows for a repo"""
        async for workflows in self._fetch_data(
            f"{self.base_url}/repos/{self._auth_client.get_user_agent()}/{repo_slug}/actions/workflows",
            values_key="workflows",
        ):
            logger.info(f"Found {len(workflows)} workflows for {repo_slug}")
            yield workflows

    async def get_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """get all teams for the current user"""
        async for teams in self._fetch_data(f"{self.base_url}/user/teams"):
            logger.info(f"Found {len(teams)} teams for current user")
            yield teams

    async def get_pull_requests(
        self,
        repo_slug: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """get pull requests for a repo"""
        async for prs in self._fetch_data(
            f"{self.base_url}/repos/{self._auth_client.get_user_agent()}/{repo_slug}/pulls"
        ):
            logger.info(f"Found {len(prs)} prs for {repo_slug}")
            yield prs
