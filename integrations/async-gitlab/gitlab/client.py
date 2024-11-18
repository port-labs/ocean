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
        self.base_url = f"{gitlab_host}/api/v4"
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

    async def send_api_request(
            self,
            endpoint: str,
            method: str = "GET",
            query_params: Optional[dict[str, Any]] = None,
            json_data: Optional[dict[str, Any]] = None,
    ) -> Response:
        logger.debug(
            f"Sending API request to {method} {endpoint} with query params: {query_params}"
        )
        try:
            self.http_client.headers.update(self.api_auth_header)
            response = await self.http_client.request(
                method=method,
                url=f"{self.base_url}/{endpoint}",
                params=query_params,
                json=json_data,
            )
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
        endpoint = f"{resource_type.value}s"

        pagination_params: dict[str, Any] = {"per_page": PAGE_SIZE, **(query_params or {})}
        while endpoint:
            try:
                response = await self.send_api_request(
                    endpoint=endpoint, query_params=pagination_params
                )
                yield response.json()

                next_page = response.headers.get('x-next-page')
                if next_page:
                    pagination_params = {"page": next_page, **(pagination_params or {})}
                else:
                    endpoint = None
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
            response = await self.send_api_request(
                endpoint=path,
                method="POST",
                json_data=payload
            )
            return response.json()
        except HTTPError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred: {str(e)}")
            raise
