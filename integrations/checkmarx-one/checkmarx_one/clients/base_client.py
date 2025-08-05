from typing import Any, Optional, AsyncGenerator, List, Dict

import httpx
from loguru import logger
from checkmarx_one.utils import IgnoredError
from port_ocean.utils import http_async_client

from checkmarx_one.exceptions import CheckmarxAuthenticationError
from checkmarx_one.auths.auth import CheckmarxAuthenticator

from urllib.parse import urljoin


PAGE_SIZE = 100


class CheckmarxOneClient:
    """
    Base HTTP client for Checkmarx One API.
    Handles common HTTP operations, error handling.
    """

    _DEFAULT_IGNORED_ERRORS = [
        IgnoredError(
            status=401,
            message="Unauthorized access to endpoint — authentication required or token invalid",
            type="UNAUTHORIZED",
        ),
        IgnoredError(
            status=403,
            message="Forbidden access to endpoint — insufficient permissions",
            type="FORBIDDEN",
        ),
        IgnoredError(
            status=404,
            message="Resource not found at endpoint",
        ),
    ]

    def __init__(
        self,
        base_url: str,
        authenticator: CheckmarxAuthenticator,
    ):
        """
        Initialize the base client.

        Args:
            base_url: Base URL for API calls (e.g., https://ast.checkmarx.net)
            authenticator: Authentication instance
        """
        self.base_url = base_url.rstrip("/")
        self.authenticator = authenticator

    @property
    async def auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests."""
        return await self.authenticator.get_auth_headers()

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        resource: str,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> bool:
        all_ignored_errors = (ignored_errors or []) + self._DEFAULT_IGNORED_ERRORS
        status_code = error.response.status_code

        for ignored_error in all_ignored_errors:
            if str(status_code) == str(ignored_error.status):
                logger.warning(
                    f"Failed to fetch resources at {resource} due to {ignored_error.message}"
                )
                return True
        return False

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> Dict[str, Any]:
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

        url = urljoin(f"{self.base_url}/api", endpoint.lstrip("/"))

        try:
            logger.debug(f"Making {method} request to {url}")

            response = await http_async_client.request(
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
                    response = await http_async_client.request(
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

            elif self._should_ignore_error(e, url, ignored_errors):
                return {}

            raise

        except httpx.HTTPError as e:
            logger.error(
                f"Unexpected HTTP error occurred while making {method} request to {url}: {str(e)}"
            )
            raise

    async def send_paginated_request(
        self,
        endpoint: str,
        object_key: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
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
                response = await self.send_api_request(endpoint, params=page_params)
                items: List[dict[str, Any]] = []
                if isinstance(response, list):
                    items = response
                elif isinstance(response, dict):
                    items = response.get("data", []) or response.get(object_key, [])

                if not items:
                    break

                yield items

                if len(items) < PAGE_SIZE:
                    break

                offset += len(items)

            except Exception as e:
                logger.error(f"Error in paginated request to {endpoint}: {str(e)}")
                break
