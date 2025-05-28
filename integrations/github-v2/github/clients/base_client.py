from typing import Any, Optional, Dict, Tuple
import time
import httpx
import asyncio
from loguru import logger
from httpx import Response
from port_ocean.utils import http_async_client

from github.clients.auth_client import AuthClient


class HTTPBaseClient:
    def __init__(self, base_url: str, token: str, endpoint: str = ""):
        """
        Initialize the base HTTP client for GitHub API.

        Args:
            base_url: Base URL for GitHub API
            token: GitHub access token
            endpoint: API endpoint to append to base URL
        """
        self.token = token
        self._client = http_async_client
        auth_client = AuthClient(token)
        self._headers = auth_client.get_headers()
        self.base_url = f"{base_url.rstrip('/')}/{endpoint.strip('/')}" if endpoint else base_url.rstrip('/')

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> Optional[Response]:
        """
        Send an API request to GitHub.

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

                if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
                    reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                    wait_time = reset_time - int(time.time()) + 1
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403 and e.response.headers.get("X-RateLimit-Remaining") == "0":
                    reset_time = int(e.response.headers.get("X-RateLimit-Reset", time.time() + 60))
                    wait_time = reset_time - int(time.time()) + 1
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                logger.warning(
                    f"HTTP error {e.response.status_code} for {method} {url}: {e.response.text}"
                )
                return None
            except httpx.HTTPError as e:
                logger.error(
                    f"HTTP error during {method} {url}: {e}", exc_info=True
                )
                raise e
