import base64
from typing import Any, AsyncGenerator, Dict, List
from aiolimiter import AsyncLimiter

import httpx
from port_ocean.utils import http_async_client
from loguru import logger
from port_ocean.utils.cache import cache_iterator_result

from port_ocean.context.ocean import ocean

BITBUCKET_EVENTS = [
    "repo:push",
    "pullrequest:created",
    "pullrequest:updated",
    "pullrequest:fulfilled",
    "pullrequest:rejected",
]


class BitbucketClient:
    def __init__(self, username: str, app_password: str, rate_limiter: AsyncLimiter):
        self.http_client = http_async_client
        self.username = username
        self.app_password = app_password
        self.base_url = ocean.integration_config["bitbucket_base_url"]
        self.headers = {}
        self.rate_limiter = rate_limiter
        self._generate_token()

    def _generate_token(self) -> None:
        credentials = f"{self.username}:{self.app_password}".encode()
        token = base64.b64encode(credentials).decode()
        self.token = token
        self.headers = {"Authorization": f"Basic {token}"}
        logger.info("Access token generated successfully")

    async def _fetch_paginated_data(
        self, endpoint: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Helper method to fetch paginated data from Bitbucket API."""
        url = f"{self.base_url}/{endpoint}"
        logger.info(f"Fetching paginated data from endpoint: {endpoint}")

        while url:
            try:
                async with self.rate_limiter:
                    logger.debug(f"Fetching data from URL: {url}")
                    response = await self.http_client.get(url, headers=self.headers)
                    response.raise_for_status()
                    data = response.json()
                    values = data.get("values", [])
                    logger.info(f"Retrieved {len(values)} items from {url}")
                    yield values
                    url = data.get("next", None)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(f"Endpoint not found (404): {url}")
                    return
                elif e.response.status_code == 401:
                    logger.error("Unauthorized access (401). Check authentication.")
                    return
                else:
                    logger.error(
                        f"HTTP error {e.response.status_code}: {e.response.text}"
                    )
                    return

    @cache_iterator_result()
    async def fetch_workspaces(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch all workspaces the user has access to."""
        async for data in self._fetch_paginated_data("workspaces"):
            yield data

    @cache_iterator_result()
    async def fetch_repositories(
        self, workspace: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch all repositories in a specific workspace."""
        async for data in self._fetch_paginated_data(f"repositories/{workspace}"):
            yield data

    async def fetch_projects(
        self, workspace: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch all projects in a specific workspace."""
        logger.debug(f"Fetching projects for workspace: {workspace}")
        async for data in self._fetch_paginated_data(
            f"workspaces/{workspace}/projects"
        ):
            yield data

    async def fetch_pull_requests(
        self, workspace: str, repo_slug: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch all pull requests for a repository in a specific workspace."""
        logger.debug(f"Fetching pull requests for repository: {repo_slug}")
        async for data in self._fetch_paginated_data(
            f"repositories/{workspace}/{repo_slug}/pullrequests"
        ):
            yield data

    async def fetch_components(
        self, workspace: str, repo_slug: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch all components for a repository in a specific workspace."""
        logger.debug(f"Fetching components for repository: {repo_slug}")
        async for data in self._fetch_paginated_data(
            f"repositories/{workspace}/{repo_slug}/components"
        ):
            yield data

    async def register_webhook(
        self, workspace: str, webhook_url: str, secret: str
    ) -> None:
        """Register a webhook for a specific workspace."""
        url = f"{self.base_url}/workspaces/{workspace}/hooks"
        payload = {
            "description": "Port Ocean Integration Webhook",
            "url": webhook_url,
            "active": True,
            "events": BITBUCKET_EVENTS,
            "secret": secret,
        }

        response = await self.http_client.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        logger.info(
            f"Webhook registered successfully for workspace {workspace}: {response.json()}"
        )
