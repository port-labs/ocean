"""Harbor API client implementation."""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from httpx import Response
from loguru import logger
from port_ocean.utils import http_async_client


class HarborClient:
    """Harbor API client using Ocean's http_async_client with built-in retry logic."""

    PAGE_SIZE = 50

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        api_version: str = "v2.0",
    ) -> None:
        """Initialize the Harbor client.

        Args:
            base_url: The Harbor base URL (e.g., 'https://harbor.example.com')
            username: The Harbor username for Basic Auth
            password: The Harbor password for Basic Auth
            api_version: The Harbor API version (default: v2.0)
        
        Raises:
            ValueError: If base_url, username, or password is empty or None
        """
        if not base_url:
            raise ValueError(
                "Harbor base_url is required but was not provided. "
                "Please set the 'baseUrl' configuration in your integration config."
            )
        if not username:
            raise ValueError(
                "Username is required for Harbor API authentication."
            )
        if not password:
            raise ValueError(
                "Password is required for Harbor API authentication."
            )
        
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version.strip("/")
        self.username = username
        self.password = password

    @property
    def api_base_url(self) -> str:
        """Get the base URL for Harbor API."""
        return f"{self.base_url}/api/{self.api_version}"

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Basic Auth."""
        import base64

        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        """Perform an HTTP request to the Harbor API and return the raw response.

        Args:
            endpoint: The API endpoint (e.g., '/projects')
            method: HTTP method (GET, POST, PUT, DELETE)
            params: Query parameters
            json_data: JSON payload for POST/PUT requests
            headers: Additional headers

        Returns:
            HTTP response object

        Raises:
            httpx.HTTPError: If the request fails after all retries
        """
        if endpoint.startswith("http"):
            url = endpoint
        else:
            normalized_endpoint = endpoint.lstrip("/")
            url = f"{self.api_base_url}/{normalized_endpoint}"

        request_headers = self._get_auth_headers()
        if headers:
            request_headers |= headers

        logger.debug(f"Making {method} request to {url}")

        try:
            response = await http_async_client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=request_headers,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error {e.response.status_code} for {method} {url}: {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {method} {url}: {e}")
            raise

    async def send_api_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Send a request to the Harbor API and return parsed JSON content."""
        response = await self._make_request(
            endpoint=endpoint,
            method=method,
            params=params,
            json_data=json_data,
            headers=headers,
        )
        return response.json()


    async def send_paginated_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[Any, None]:
        """Handle Harbor's pagination for API requests.

        Args:
            endpoint: The API endpoint
            params: Query parameters
            method: HTTP method

        Yields:
            Raw JSON response from each page (list or dict)
        """
        if params is None:
            params = {}

        page = 1

        logger.info(f"Starting pagination for {method} {endpoint}")

        while True:
            request_params = {**params, "page": page, "page_size": self.PAGE_SIZE}

            response = await self._make_request(
                endpoint,
                method=method,
                params=request_params,
            )

            if not response:
                break

            response_data = response.json()

            if not response_data:
                logger.debug(f"No data found on page {page} for {endpoint}")
                break

            yield response_data

            # Check if we've reached the last page by checking response size
            # If response is a list, check its length
            # If response is a dict, we can't determine page size, so we'll continue
            # and let the exporter handle it
            if isinstance(response_data, list) and len(response_data) < self.PAGE_SIZE:
                logger.debug(f"Last page reached for {endpoint}")
                break

            page += 1

