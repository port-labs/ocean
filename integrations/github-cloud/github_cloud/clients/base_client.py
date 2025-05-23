from typing import Any, Optional, Dict
import asyncio
import time
from http import HTTPStatus

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from github_cloud.clients.auth_client import AuthClient


class HTTPBaseClient:
    def __init__(self, base_url: str, token: str, endpoint: str = "", client: Optional[httpx.AsyncClient] = None):
        """
        Initialize the base HTTP client for GitHub Cloud API.

        Args:
            base_url: Base URL for GitHub Cloud API
            token: GitHub Cloud access token
            endpoint: API endpoint to append to base URL
            client: Optional HTTP client to use (for testing)
        """
        self.token = token
        self._client = client or http_async_client
        auth_client = AuthClient(token)
        self._headers = auth_client.get_headers()
        self.base_url = f"{base_url.rstrip('/')}/{endpoint.strip('/')}" if endpoint else base_url.rstrip('/')

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Send an API request to GitHub Cloud.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path to append to base URL
            params: Query parameters
            data: Request body data

        Returns:
            JSON response as dictionary

        Raises:
            httpx.HTTPError: If the request fails (except 404)
            httpx.HTTPStatusError: If the request fails with a non-404 status code
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        logger.debug(f"Sending {method} request to {url}")

        for attempt in range(3):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    params=params,
                    json=data,
                )

                # Handle rate limiting using match-case
                match response.status_code:
                    case HTTPStatus.FORBIDDEN if response.headers.get("X-RateLimit-Remaining") == "0":
                        reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                        wait_time = reset_time - int(time.time()) + 1
                        logger.warning(f"Rate limited. Waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    case HTTPStatus.NOT_FOUND:
                        return {}
                    case _:
                        response.raise_for_status()
                        return response.json() if response.content else {}

            except httpx.HTTPStatusError as e:
                # Handle rate limiting in exception case
                if e.response.status_code == HTTPStatus.FORBIDDEN and e.response.headers.get("X-RateLimit-Remaining") == "0":
                    reset_time = int(e.response.headers.get("X-RateLimit-Reset", time.time() + 60))
                    wait_time = reset_time - int(time.time()) + 1
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                raise

            except httpx.HTTPError as e:
                logger.error(f"HTTP error occurred: {str(e)}")
                raise

    async def get_page_links(self, response: httpx.Response) -> Dict[str, str]:
        """
        Parse GitHub Cloud API pagination links from response headers.

        Args:
            response: The HTTP response

        Returns:
            Dictionary of link relations to URLs
        """
        if "Link" not in response.headers:
            return {}

        return {
            rel.split('rel="')[1].rstrip('"'): parts[0].strip("<>")
            for link in response.headers["Link"].split(",")
            if len(parts := link.strip().split(";")) >= 2
            and 'rel="' in (rel := parts[1].strip())
        }
