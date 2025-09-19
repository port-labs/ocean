"""Okta API client implementation."""

import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from loguru import logger

import httpx
from httpx import Response, Timeout
from port_ocean.utils import http_async_client


class OktaClient:
    """Okta API client."""

    # Okta uses Link headers for pagination
    NEXT_PATTERN = re.compile(r'<([^>]+)>; rel="next"')
    PAGE_SIZE = 200  # Okta's default page size

    def __init__(
        self,
        okta_domain: str,
        api_token: str,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize the Okta client.

        Args:
            okta_domain: The Okta domain (e.g., 'dev-123456.okta.com')
            api_token: The Okta API token
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.okta_domain = okta_domain.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.max_retries = max_retries

        # Configure shared Ocean async HTTP client
        http_async_client.timeout = Timeout(timeout)

    @property
    def base_url(self) -> str:
        """Get the base URL for Okta API."""
        return f"https://{self.okta_domain}/api/v1"

    async def make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        """Make an HTTP request to the Okta API.

        Args:
            endpoint: The API endpoint (e.g., '/users')
            method: HTTP method (GET, POST, PUT, DELETE)
            params: Query parameters
            json_data: JSON payload for POST/PUT requests
            headers: Additional headers

        Returns:
            HTTP response object

        Raises:
            httpx.HTTPError: If the request fails after all retries
        """
        # Build URL safely without losing "/api/v1" segment
        normalized_endpoint = endpoint.lstrip("/")
        base = self.base_url.rstrip("/")
        url = f"{base}/{normalized_endpoint}"

        # Build request headers per request to avoid global mutation of shared client
        request_headers: Dict[str, str] = {
            "Authorization": f"SSWS {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Port-Ocean-Okta-Integration/1.0",
        }
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

    def _get_next_link(self, link_header: str) -> Optional[str]:
        """Extract the URL from the 'next' link in an Okta Link header."""
        match = self.NEXT_PATTERN.search(link_header)
        return match.group(1) if match else None

    async def send_paginated_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Handle Okta's pagination for API requests.

        Args:
            endpoint: The API endpoint
            params: Query parameters
            method: HTTP method

        Yields:
            List of items from each page
        """
        if params is None:
            params = {}

        # Set page size for optimal performance
        params["limit"] = self.PAGE_SIZE

        logger.info(f"Starting pagination for {method} {endpoint}")

        while True:
            response = await self.make_request(
                endpoint,
                method=method,
                params=params,
            )

            if not response or not (items := response.json()):
                break

            yield items

            # Check for next page using Link header
            if not (link_header := response.headers.get("Link")) or not (
                next_url := self._get_next_link(link_header)
            ):
                break

            # Extract endpoint from next URL
            endpoint = next_url.replace(self.base_url.rstrip("/"), "").lstrip("/")
            params = None  # Reset params as they're included in the next URL
