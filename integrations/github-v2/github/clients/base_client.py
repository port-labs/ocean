from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, List, Optional, Dict

from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
import httpx
from httpx import Response


class AbstractGithubClient(ABC):
    def __init__(
        self,
        token: str,
        organization: str,
        github_host: str,
        webhook_secret: str | None,
    ) -> None:
        self.organization = organization
        self.github_host = github_host
        self.webhook_secret = webhook_secret
        self.client = http_async_client
        self.base_url = github_host.rstrip("/")

        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.client.headers.update(self.headers)

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Send request to GitHub API with error handling and rate limiting."""
        url = f"{self.base_url}/{endpoint}"

        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
            )
            response.raise_for_status()

            logger.debug(f"Successfully fetched {method} {endpoint}")

            return response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Resource not found at endpoint '{endpoint}'")
                return e.response
            logger.error(
                f"GitHub API error for endpoint '{endpoint}': Status {e.response.status_code}, "
                f"Method: {method}, Response: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for endpoint '{endpoint}': {str(e)}")
            raise

    @abstractmethod
    async def get_single_resource(
        self, object_type: str, identifier: str
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def create_or_update_webhook(
        self, base_url: str, webhook_events: List[str]
    ) -> None: ...

    @abstractmethod
    def get_paginated_resources(
        self,
        resource_type: str,
        query_params: Optional[dict[str, Any]] = None,
        path_params: Optional[dict[str, str]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]: ...

    @cache_iterator_result()
    @abstractmethod
    def get_repositories(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]: ...
