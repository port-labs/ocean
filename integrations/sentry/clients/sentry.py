import asyncio
import time
from typing import Any, AsyncGenerator, AsyncIterator, cast
from loguru import logger

from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from integration import SentryResourceConfig
from port_ocean.context.event import event

import httpx

MAXIMUM_CONCURRENT_REQUESTS = 20
MAXIMUM_CONCURRENT_REQUESTS_ISSUES = 3
MINIMUM_LIMIT_REMAINING = 10
MINIMUM_ISSUES_LIMIT_REMAINING = 3
DEFAULT_SLEEP_TIME = 0.1
PAGE_SIZE = 100


class ResourceNotFoundError(Exception):
    pass


class SentryClient:
    def __init__(
        self,
        sentry_base_url: str,
        auth_token: str,
        sentry_organization: str,
        default_semaphore: asyncio.Semaphore,
        issues_semaphore: asyncio.Semaphore | None,
    ) -> None:
        self.sentry_base_url = sentry_base_url
        self.auth_token = auth_token
        self.base_headers = {"Authorization": "Bearer " + f"{self.auth_token}"}
        self.api_url = f"{self.sentry_base_url}/api/0"
        self.organization = sentry_organization
        self.client = http_async_client
        self.client.headers.update(self.base_headers)
        self.selector = cast(SentryResourceConfig, event.resource_config).selector
        self.default_semaphore = default_semaphore
        self.issues_semaphore = issues_semaphore

    async def fetch_with_rate_limit_handling(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> httpx.Response:
        """Rate limit handler
        This method makes sure requests aren't abusing Sentry's rate-limits.
        It references:
        Requests per "window" - By adding a sleep after each request that had a RATE_LIMIT_REMAINING below a threshold
        for more information about Sentry's rate limits, please check out https://docs.sentry.io/api/ratelimits/
        """
        if not semaphore:
            semaphore = self.default_semaphore
        while True:
            async with semaphore:
                response = await self.client.get(url, params=params)
            rate_limit_remaining = int(
                response.headers["X-Sentry-Rate-Limit-Remaining"]
            )
            if rate_limit_remaining <= MINIMUM_ISSUES_LIMIT_REMAINING:
                rate_limit_reset = int(response.headers["X-Sentry-Rate-Limit-Reset"])
                current_time = int(time.time())
                wait_time = (
                    rate_limit_reset - current_time
                    if rate_limit_reset > current_time
                    else DEFAULT_SLEEP_TIME
                )
                logger.info(
                    f"Approaching rate limit. Waiting for {wait_time} seconds before retrying. "
                    f"URL: {url}, Remaining: {rate_limit_remaining} "
                )
                await asyncio.sleep(wait_time)
            return response

    def get_next_link(self, link_header: str) -> str:
        """Information about the next page of results is provided in the link header. The pagination cursors are returned for both the previous and the next page.
        One of the URLs in the link response has rel=next, which indicates the next results page. It also has results=true, which means that there are more results.
        You can find more information about pagination in Sentry here: https://docs.sentry.io/api/pagination/
        """
        if link_header:
            links = link_header.split(",")
            for link in links:
                parts = link.strip().split(";")
                url = parts[0].strip("<>")
                rel = parts[1].strip()
                results = parts[2].strip()
                if 'rel="next"' in rel and 'results="true"' in results:
                    return url
        return ""

    async def get_paginated_resource(
        self, url: str, custom_semaphore: asyncio.Semaphore | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params: dict[str, Any] = {"per_page": PAGE_SIZE}

        logger.debug(f"Getting paginated resource from Sentry for URL: {url}")

        while url:
            try:
                response = await self.fetch_with_rate_limit_handling(
                    url=url, params=params, semaphore=custom_semaphore
                )
                response.raise_for_status()
                records = response.json()
                logger.debug(
                    f"Received {len(records)} records from Sentry for URL: {url}"
                )
                yield records

                url = self.get_next_link(response.headers.get("link", ""))

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP occurred while fetching Sentry data: {e}")
                raise

    async def get_single_resource(self, url: str) -> list[dict[str, Any]]:
        logger.debug(f"Getting single resource from Sentry for URL: {url}")
        try:
            response = await self.fetch_with_rate_limit_handling(url=url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code:
                raise ResourceNotFoundError()
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            return []
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching Sentry data: {e}")
            return []

    @cache_iterator_result()
    async def get_paginated_projects(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for project in self.get_paginated_resource(f"{self.api_url}/projects/"):
            yield project

    @cache_iterator_result()
    async def get_paginated_project_slugs(self) -> AsyncGenerator[list[str], None]:
        async for projects in self.get_paginated_projects():
            project_slugs = [project["slug"] for project in projects]
            yield project_slugs

    async def get_paginated_issues(
        self, project_slug: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for issues in self.get_paginated_resource(
            f"{self.api_url}/projects/{self.organization}/{project_slug}/issues/",
            custom_semaphore=self.issues_semaphore,
        ):
            yield issues

    async def get_project_tags(self, project_slug: str) -> list[dict[str, Any]]:
        try:
            url = f"{self.api_url}/projects/{self.organization}/{project_slug}/tags/{self.selector.tag}/values/"
            return await self.get_single_resource(url)
        except ResourceNotFoundError:
            logger.debug(f"Found no {project_slug} in {self.organization}")
            return []

    async def get_issue_tags(self, issue_id: str) -> list[dict[str, Any]]:
        try:
            url = f"{self.api_url}/organizations/{self.organization}/issues/{issue_id}/tags/{self.selector.tag}/values/"
            return await self.get_single_resource(url)
        except ResourceNotFoundError:
            logger.debug(f"Found no issues in {self.organization}")
            return []

    async def get_issue_tags_iterator(
        self, issue: dict[str, Any]
    ) -> AsyncIterator[list[dict[str, Any]]]:
        tags = await self.get_issue_tags(issue["id"])
        yield [{**issue, "__tags": tags}]

    async def get_project_tags_iterator(
        self, project: dict[str, Any]
    ) -> AsyncIterator[list[dict[str, Any]]]:
        tags = await self.get_project_tags(project["slug"])
        yield [{**project, "__tags": tag} for tag in tags]
