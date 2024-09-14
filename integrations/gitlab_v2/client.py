import asyncio
import httpx
from httpx import Timeout
from loguru import logger
from typing import Any, AsyncGenerator, Optional
from port_ocean.utils import http_async_client
from port_ocean.context.ocean import ocean
from port_ocean.utils.cache import cache_iterator_result

REQUEST_TIMEOUT: int = 60

class GitlabClient:
    def __init__(self, gitlab_host: str, gitlab_token: str) -> None:
        self.gitlab_host = gitlab_host
        self.gitlab_token = gitlab_token
        self.client = http_async_client
        self.authorization_header = {"Authorization": f"Bearer {gitlab_token}"}
        self.client.headers.update(self.authorization_header)
        self.client.timeout = Timeout(REQUEST_TIMEOUT)

    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.info(f"Sending request to GitLab API: {method} {url}")
        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_data,
                headers=headers,
            )
            response.raise_for_status()

            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Encountered an HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a request to {method} {url} with query_params: {query_params}"
            )
            raise

    @staticmethod
    def _default_paginated_req_params(
            page: int = 1, per_page: int = 50, owned: bool = True
    ) -> dict[str, Any]:
        return {
            "page": page,
            "per_page": per_page,
            "owned": owned,
        }

    async def _make_paginated_request(
        self, url: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[dict[str, list[dict[str, Any]]], None]:
        params = {**self._default_paginated_req_params(), **params}
        while True:
            logger.info(f"Making paginated request to {url} with params: {params}")
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                response_data = response.json()

                yield response_data

                # Check if there's a next page
                next_page = response.headers.get("X-Next-Page")
                if not next_page:
                    logger.info("No more pages to fetch, stopping pagination.")
                    break  # No more pages, exit the loop

                params["page"] = int(next_page)
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code}"
                    f" and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP occurred while fetching data {e}")
                raise

        logger.info("Finished paginated request")
        return
