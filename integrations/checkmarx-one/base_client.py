import asyncio
from typing import Any, Optional

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from port_ocean.utils import http_async_client

from exceptions import CheckmarxAuthenticationError, CheckmarxAPIError
from auth import CheckmarxAuthenticator


PAGE_SIZE = 100
MAXIMUM_CONCURRENT_REQUESTS = 10
DEFAULT_RATE_LIMIT_PER_HOUR = 3600  # Conservative default


class BaseCheckmarxClient:
    """
    Base HTTP client for Checkmarx One API.
    Handles common HTTP operations, error handling, and rate limiting.
    """

    def __init__(
        self,
        base_url: str,
        authenticator: CheckmarxAuthenticator,
        rate_limiter: Optional[AsyncLimiter] = None,
    ):
        """
        Initialize the base client.

        Args:
            base_url: Base URL for API calls (e.g., https://ast.checkmarx.net)
            authenticator: Authentication instance
            rate_limiter: Custom rate limiter instance
        """
        self.base_url = base_url.rstrip("/")
        self.authenticator = authenticator

        # HTTP client setup
        self.http_client = http_async_client
        self.http_client.timeout = httpx.Timeout(30)

        # Rate limiting
        if rate_limiter is None:
            rate_limiter = AsyncLimiter(DEFAULT_RATE_LIMIT_PER_HOUR, 3600)
        self.rate_limiter = rate_limiter
        self._semaphore = asyncio.Semaphore(MAXIMUM_CONCURRENT_REQUESTS)

    @property
    async def auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests."""
        return await self.authenticator.get_auth_headers()

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Send a request to the Checkmarx One API with proper error handling.

        Args:
            endpoint: API endpoint path (e.g., "/projects")
            method: HTTP method
            params: Query parameters
            json_data: JSON body data

        Returns:
            API response as dictionary
        """
        from urllib.parse import urljoin

        url = urljoin(f"{self.base_url}/api", endpoint.lstrip("/"))

        async with self.rate_limiter:
            async with self._semaphore:
                try:
                    logger.debug(f"Making {method} request to {url}")

                    response = await self.http_client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_data,
                        headers=await self.auth_headers,
                    )

                    response.raise_for_status()
                    return response.json()

                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code
                    response_text = e.response.text

                    logger.error(
                        f"HTTP error {status_code} for {method} {url}: {response_text}"
                    )

                    if status_code == 401:
                        # Try to refresh token once
                        logger.info("Received 401, attempting to refresh token")
                        try:
                            await self.authenticator.refresh_token()
                            # Retry the request with new token
                            response = await self.http_client.request(
                                method=method,
                                url=url,
                                params=params,
                                json=json_data,
                                headers=await self.auth_headers,
                            )
                            response.raise_for_status()
                            return response.json()
                        except Exception:
                            raise CheckmarxAuthenticationError(
                                "Authentication failed after token refresh"
                            )

                    elif status_code == 403:
                        raise CheckmarxAPIError(
                            "Access denied. Please check your permissions."
                        )
                    elif status_code == 404:
                        logger.warning(f"Resource not found: {url}")
                        return {}
                    elif status_code == 429:
                        logger.warning(
                            "Rate limit exceeded. Consider reducing request frequency."
                        )
                        raise CheckmarxAPIError("Rate limit exceeded")
                    else:
                        raise CheckmarxAPIError(f"API request failed: {response_text}")

                except Exception as e:
                    logger.error(
                        f"Unexpected error during API request to {url}: {str(e)}"
                    )
                    raise CheckmarxAPIError(f"Request failed: {str(e)}")

    async def _get_paginated_resources(
        self,
        endpoint: str,
        object_key: str,
        params: Optional[dict[str, Any]] = None,
    ):
        """
        Get paginated resources from Checkmarx One API.

        Args:
            endpoint: API endpoint path
            object_key: Key in response containing the items
            params: Additional query parameters

        Yields:
            Batches of resources
        """
        if params is None:
            params = {}

        offset: int = 0

        while True:
            page_params = {
                **params,
                "limit": PAGE_SIZE,
                "offset": offset,
            }

            try:
                response = await self._send_api_request(endpoint, params=page_params)
                # Handle different response formats
                items: list[dict[str, Any]] = []
                if isinstance(response, list):
                    items = response
                elif isinstance(response, dict):
                    # Try common pagination patterns
                    items = (
                        response.get("data", []) or response.get(object_key, []) or []
                    )

                if not items:
                    break

                yield items

                # Check if we have more data
                if len(items) < PAGE_SIZE:
                    break

                offset += len(items)

            except Exception as e:
                logger.error(f"Error in paginated request to {endpoint}: {str(e)}")
                break
