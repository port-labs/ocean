from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional, Dict

from port_ocean.utils import http_async_client
from loguru import logger
import httpx
from httpx import Response


class AbstractGithubClient(ABC):
    def __init__(
        self,
        token: str,
        organization: str,
        github_host: str,
    ) -> None:
        self.organization = organization
        self.github_host = github_host
        self.client = http_async_client
        self.base_url = github_host.rstrip("/")

        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.client.headers.update(self.headers)

    async def send_api_request(
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
    def send_paginated_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[list[dict[str, Any]], None]: ...
