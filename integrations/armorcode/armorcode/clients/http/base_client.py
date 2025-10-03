from abc import ABC
from typing import Any, Dict, Optional, AsyncGenerator, List
from httpx import HTTPStatusError, AsyncClient
import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from armorcode.clients.auth.abstract_authenticator import AbstractArmorcodeAuthenticator
from armorcode.helpers.utils import IgnoredError

PAGE_SIZE = 100


class BaseArmorcodeClient(ABC):
    """Base client for ArmorCode API interactions."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "tags": "",
        "sortBy": "NAME",
        "direction": "ASC",
    }

    _DEFAULT_IGNORED_ERRORS = [
        IgnoredError(
            status=401,
            message="Unauthorized access to endpoint — authentication required or token invalid",
        ),
        IgnoredError(
            status=403,
            message="Forbidden access to endpoint — insufficient permissions",
        ),
        IgnoredError(
            status=404,
            message="Resource not found at endpoint",
        ),
    ]

    def __init__(self, base_url: str, authenticator: AbstractArmorcodeAuthenticator):
        self.base_url = base_url.rstrip("/")
        self.authenticator = authenticator
        self.http_client: AsyncClient = http_async_client

    @property
    async def headers(self) -> Dict[str, str]:
        """Build and return headers for ArmorCode API requests."""
        return (await self.authenticator.get_headers()).as_dict()

    def _should_ignore_error(
        self,
        error: HTTPStatusError,
        endpoint: str,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> bool:
        """Check if an error should be ignored based on the provided ignored errors list."""
        ignored_errors = (ignored_errors or []) + self._DEFAULT_IGNORED_ERRORS

        for ignored_error in ignored_errors:
            if str(ignored_error.status) == str(error.response.status_code):
                logger.warning(
                    f"Failed to fetch resources at {endpoint} due to {ignored_error.message}. Error Message: {error.response.text}"
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
        """Send an authenticated API request to the ArmorCode API."""
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
            if self._should_ignore_error(e, endpoint, ignored_errors):
                return {}

            logger.error(
                f"ArmorCode API error for endpoint '{endpoint}': Status {e.response.status_code}, "
                f"Method: {method}, Response: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during API request to {url}: {str(e)}")
            raise

    async def _send_offset_paginated_request(
        self,
        endpoint: str,
        method: str,
        json_data: Optional[Dict[str, Any]],
        ignored_errors: Optional[List[IgnoredError]],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send offset-based paginated API requests to the ArmorCode API."""
        page_number = 0

        while True:
            params = {
                **self.DEFAULT_PARAMS,
                "pageNumber": page_number,
                "pageSize": PAGE_SIZE,
            }

            response = await self.send_api_request(
                endpoint,
                method=method,
                params=params,
                json_data=json_data,
                ignored_errors=ignored_errors,
            )

            if not response:
                break

            items = response["content"]
            if not isinstance(items, list):
                logger.error(
                    f"Invalid items returned for {endpoint} on page {page_number}"
                )
                break

            if not items:
                logger.info(f"No items returned for {endpoint} on page {page_number}")
                break

            logger.info(
                f"Fetched {len(items)} items from {endpoint} on page {page_number}"
            )
            yield items

            if response["last"]:
                break

            page_number += 1

    async def _send_cursor_paginated_request(
        self,
        endpoint: str,
        method: str,
        json_data: Optional[Dict[str, Any]],
        ignored_errors: Optional[List[IgnoredError]],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send cursor-based paginated API requests to the ArmorCode API."""

        params = {**self.DEFAULT_PARAMS, "size": PAGE_SIZE}

        while True:
            response = await self.send_api_request(
                endpoint,
                method=method,
                params=params,
                json_data=json_data,
                ignored_errors=ignored_errors,
            )

            if not response:
                break

            container: Dict[str, Any] = response["data"]
            items = container["findings"]
            if not isinstance(items, list):
                logger.error(f"Unexpected response format for {endpoint}")
                break

            if not items:
                logger.info(f"No items returned for {endpoint}")
                break

            logger.info(f"Fetched {len(items)} items from {endpoint}")
            yield items

            after_key = container["afterKey"]
            logger.debug(f"After key for {endpoint}: {after_key}")

            if after_key < 0:
                break

            params = {**params, "afterKey": after_key}

    async def send_paginated_request(
        self,
        endpoint: str,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        use_offset_pagination: bool = True,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send paginated API requests to the ArmorCode API."""
        if use_offset_pagination:
            async for items in self._send_offset_paginated_request(
                endpoint,
                method,
                json_data,
                ignored_errors,
            ):
                yield items
        else:
            async for items in self._send_cursor_paginated_request(
                endpoint, method, json_data, ignored_errors
            ):
                yield items
