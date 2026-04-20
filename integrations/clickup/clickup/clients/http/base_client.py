from abc import ABC
from typing import Any, Dict, Optional, AsyncGenerator, List

import httpx
from httpx import HTTPStatusError, AsyncClient
from loguru import logger
from port_ocean.utils import http_async_client

from clickup.clients.auth.abstract_authenticator import AbstractClickUpAuthenticator
from clickup.helpers.utils import IgnoredError

PAGE_SIZE = 100


class BaseClickUpClient(ABC):
    """Base HTTP client for ClickUp API interactions.

    This class handles:
    - HTTP request sending
    - Rate limiting awareness (100 req/min for standard plans)
    - Error handling with configurable ignored errors
    - Page-based pagination (ClickUp uses page parameter starting at 0)

    This class does NOT handle:
    - Resource-specific endpoints (use Exporters)
    - Data transformation (use Exporters)
    - Business logic (use Exporters)

    Rate Limits (per API docs):
    - Free Forever, Unlimited, Business: 100 requests/minute
    - Business Plus: 1,000 requests/minute
    - Enterprise: 10,000 requests/minute

    Reference: https://developer.clickup.com/docs/rate-limits
    """

    _DEFAULT_IGNORED_ERRORS = [
        IgnoredError(
            status=401,
            message="Unauthorized: Invalid or expired API token",
        ),
        IgnoredError(
            status=403,
            message="Forbidden: Insufficient permissions for this resource",
        ),
        IgnoredError(
            status=404,
            message="Resource not found",
        ),
    ]

    def __init__(
        self,
        base_url: str,
        authenticator: AbstractClickUpAuthenticator,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.authenticator = authenticator
        self.http_client: AsyncClient = http_async_client

    @property
    async def headers(self) -> Dict[str, str]:
        """Build and return headers for ClickUp API requests."""
        return (await self.authenticator.get_headers()).as_dict()

    def _should_ignore_error(
        self,
        error: HTTPStatusError,
        endpoint: str,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> bool:
        """Check if an error should be ignored based on the provided list."""
        all_ignored = (ignored_errors or []) + self._DEFAULT_IGNORED_ERRORS

        status_code = error.response.status_code
        for ignored_error in all_ignored:
            if int(ignored_error.status) == status_code:
                err_msg = None
                try:
                    data = error.response.json()
                    err_msg = data.get("err") or data.get("error") or data.get("ECODE")
                except Exception:
                    pass

                if not err_msg:
                    err_msg = error.response.text or f"HTTP {status_code}"

                logger.warning(
                    f"Ignoring error for {endpoint}: {ignored_error.message}. "
                    f"Details: {err_msg}"
                )
                return True
        return False

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> Dict[str, Any]:
        """Send an authenticated API request to the ClickUp API.

        Args:
            endpoint: API endpoint path (e.g., "/v2/team")
            method: HTTP method (GET, POST, PUT, DELETE)
            params: Query parameters
            json_data: JSON body data
            ignored_errors: Additional errors to ignore

        Returns:
            Parsed JSON response as dictionary, or empty dict if ignored error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=await self.headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            if e.response.status_code == 429:
                reset_time = e.response.headers.get("X-RateLimit-Reset", "unknown")
                logger.error(
                    f"Rate limit exceeded for {endpoint}. "
                    f"Resets at: {reset_time}. "
                    f"Consider upgrading ClickUp plan for higher limits."
                )
                raise

            if self._should_ignore_error(e, endpoint, ignored_errors):
                return {}

            logger.error(
                f"ClickUp API error for '{endpoint}': "
                f"Status {e.response.status_code}, "
                f"Method: {method}, Response: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during API request to {url}: {str(e)}")
            raise

    async def send_paginated_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data_key: str = "tasks",
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send page-based paginated API requests to the ClickUp API.

        ClickUp uses page-based pagination with:
        - `page` parameter starting at 0
        - 100 items per page (for tasks)
        - `last_page` boolean in response indicating if more pages exist

        Args:
            endpoint: API endpoint path
            params: Additional query parameters
            data_key: Key in response containing the items array
            ignored_errors: Additional errors to ignore

        Yields:
            Batches of items from each page
        """
        page = 0
        base_params = params or {}

        while True:
            current_params = {**base_params, "page": page}

            response = await self.send_api_request(
                endpoint,
                method="GET",
                params=current_params,
                ignored_errors=ignored_errors,
            )

            if not response:
                break

            items = response.get(data_key, [])
            if not isinstance(items, list):
                logger.error(
                    f"Expected list for '{data_key}' in {endpoint}, "
                    f"got {type(items).__name__}"
                )
                break

            if not items:
                logger.debug(f"No items returned for {endpoint} on page {page}")
                break

            logger.info(f"Fetched {len(items)} items from {endpoint} on page {page}")
            yield items

            is_last_page = response.get("last_page", True)
            if is_last_page:
                break

            page += 1
