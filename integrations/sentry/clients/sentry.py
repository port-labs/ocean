from typing import Any, AsyncGenerator
from loguru import logger

from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
import httpx

PAGE_SIZE = 100


class SentryClient:
    def __init__(
        self, sentry_base_url: str, auth_token: str, sentry_organization: str
    ) -> None:
        self.sentry_base_url = sentry_base_url
        self.auth_token = auth_token
        self.base_headers = {"Authorization": "Bearer " + f"{self.auth_token}"}
        self.api_url = f"{self.sentry_base_url}/api/0"
        self.organization = sentry_organization
        self.client = http_async_client
        self.client.headers.update(self.base_headers)

    def get_next_link(self, link_header: str) -> str:
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
        self, url: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params: dict[str, Any] = {"per_page": PAGE_SIZE}

        while url:
            try:
                response = await self.client.get(
                    url=url,
                    params=params,
                )
                response.raise_for_status()
                records = response.json()
                logger.info(
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

    @cache_iterator_result("project")
    async def get_paginated_projects(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting paginated projects from Sentry")
        async for project in self.get_paginated_resource(f"{self.api_url}/projects/"):
            yield project

    async def get_paginated_issues(
        self, project_slug: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Getting paginated issues from Sentry for project {project_slug}")

        async for issues in self.get_paginated_resource(
            f"{self.api_url}/projects/{self.organization}/{project_slug}/issues/"
        ):
            yield issues
