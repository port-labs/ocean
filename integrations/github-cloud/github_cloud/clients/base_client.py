from typing import Any, Optional, Dict
import asyncio
import time

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

                 # Handle rate limiting
                if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
                    reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                    wait_time = reset_time - int(time.time()) + 1
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json() if response.content else {}

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return {}
                if e.response.status_code == 403 and e.response.headers.get("X-RateLimit-Remaining") == "0":
                    reset_time = int(e.response.headers.get("X-RateLimit-Reset", time.time() + 60))
                    wait_time = reset_time - int(time.time()) + 1
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                raise

            except httpx.HTTPError:
                raise

    async def get_page_links(self, response: httpx.Response) -> Dict[str, str]:
        """
        Parse GitHub Cloud API pagination links from response headers.

        Args:
            response: The HTTP response

        Returns:
            Dictionary of link relations to URLs
        """
        links = {}

        if "Link" not in response.headers:
            return links

        for link in response.headers["Link"].split(","):
            parts = link.strip().split(";")
            if len(parts) < 2:
                continue

            url = parts[0].strip("<>")
            rel = parts[1].strip()

            if 'rel="' in rel:
                rel_type = rel.split('rel="')[1].rstrip('"')
                links[rel_type] = url

        return links
