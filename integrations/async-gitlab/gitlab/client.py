from typing import Any, AsyncGenerator, Optional, Dict
from httpx import HTTPStatusError, HTTPError, Response
from loguru import logger
import re
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from gitlab.helpers.utils import ObjectKind, RESOURCE_API_VERSIONS
from gitlab.helpers.ratelimiter import GitLabRateLimiter

PAGE_SIZE = 100


class GitLabClient(GitLabRateLimiter):
    def __init__(self, gitlab_host: str, access_token: str) -> None:
        super().__init__(gitlab_host, access_token)
        self.token = access_token
        self.api_url = f"{gitlab_host}/api"
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {"Authorization": f"Bearer {self.token}"}

    @classmethod
    def create_from_ocean_config(cls) -> "GitLabClient":
        if cache := event.attributes.get("async_gitlab_client"):
            return cache
        gitlab_client = cls(
            ocean.integration_config["gitlab_host"],
            ocean.integration_config["access_token"],
        )
        event.attributes["async_gitlab_client"] = gitlab_client
        return gitlab_client

    async def get_single_resource(
        self,
        url: str,
        query_params: Optional[dict[str, Any]] = None,
    ) -> Response:
        try:
            self.http_client.headers.update(self.api_auth_header)
            response = await self.http_client.get(url=url, params=query_params)
            response.raise_for_status()
            return response

        except HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except HTTPError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
            raise

    @cache_iterator_result()
    async def get_paginated_resources(
        self, resource_type: ObjectKind, query_params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self.api_url}/v4/{resource_type.value}s"

        pagination_params: dict[str, Any] = {"per_page": PAGE_SIZE, **(query_params or {})}
        while url:
            try:
                logger.info(
                    f"Fetching data from {url} with query params {pagination_params}"
                )
                response = await self.get_single_resource(
                    url=url, query_params=pagination_params
                )
                yield response.json()

                if response.headers.get('x-next-page'):
                    link_header = response.headers.get('link')

                    rel = "next"
                    pattern = re.compile(r'<([^>]+)>;\s*rel="%s"' % rel)
                    match = pattern.search(link_header)

                    if match:
                        url = await match.group(1)
            except HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except HTTPError as e:
                logger.error(f"HTTP error occurred: {str(e)}")
                raise

    @cache_iterator_result()
    async def get_resources(
        self,
        resource_type: ObjectKind,
        query_params: Optional[Dict[str, str]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async with self.limiter:
            async for resources in self.get_paginated_resources(
                    resource_type=resource_type,
                    query_params=query_params
            ):
                yield resources

    async def create_resource(
        self,
        path: str,
        payload: Dict
    ) -> Response:
        try:
            url = f"{self.api_url}/v4/{path}"

            self.http_client.headers.update(self.api_auth_header)
            response = await self.http_client.post(url=url, json=payload)
            response.raise_for_status()
            return response

        except HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except HTTPError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
            raise
