from abc import ABC
from typing import Any, Dict, Optional, AsyncGenerator, List
from httpx import HTTPStatusError, AsyncClient
from loguru import logger
from port_ocean.utils import http_async_client

from armorcode.clients.auth.abstract_authenticator import AbstractArmorcodeAuthenticator
from armorcode.helpers.utils import IgnoredError


class BaseArmorcodeClient(ABC):
    """Base client for ArmorCode API interactions."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "pageSize": 100,
        "tags": "",
        "sortBy": "NAME",
        "direction": "ASC",
    }

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
            type="NOT_FOUND",
        ),
    ]

    def __init__(self, base_url: str, authenticator: AbstractArmorcodeAuthenticator):
        self.base_url = base_url.rstrip("/")
        self.authenticator = authenticator
        self.http_client: AsyncClient = http_async_client

    def _should_ignore_error(
        self,
        error: HTTPStatusError,
        endpoint: str,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> bool:
        """Check if an error should be ignored based on the provided ignored errors list."""
        ignored_errors = ignored_errors or []
        ignored_errors.extend(self._DEFAULT_IGNORED_ERRORS)

        for ignored_error in ignored_errors:
            if ignored_error.status == error.response.status_code and (
                ignored_error.type is None or ignored_error.type in str(error)
            ):
                logger.warning(
                    f"{ignored_error.message} for endpoint '{endpoint}': {str(error)}"
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

        headers = self.authenticator.get_headers().as_dict()
        auth_params = self.authenticator.get_auth_params().as_dict()

        if params is None:
            params = {}
        params.update(auth_params)

        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
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
        except Exception as e:
            logger.error(f"Unexpected error during API request to {url}: {e}")
            raise

    async def _send_offset_paginated_request(
        self,
        endpoint: str,
        content_key: str,
        method: str,
        json_data: Optional[Dict[str, Any]],
        is_last_key: Optional[str],
        ignored_errors: Optional[List[IgnoredError]],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send offset-based paginated API requests to the ArmorCode API."""
        page_number = 0

        while True:
            try:
                params = {**self.DEFAULT_PARAMS, "pageNumber": page_number}

                response = await self.send_api_request(
                    endpoint,
                    method=method,
                    params=params,
                    json_data=json_data,
                    ignored_errors=ignored_errors,
                )

                container: Dict[str, Any] = (
                    response.get("data", {})
                    if isinstance(response.get("data"), dict)
                    else response
                )
                items = container.get(content_key, [])

                if not isinstance(items, list):
                    break

                if not items:
                    logger.info(
                        f"No items returned for {endpoint} on page {page_number}"
                    )
                    break

                logger.info(f"Fetched {len(items)} items from {endpoint}")
                yield items

                last_page = (
                    True
                    if is_last_key is None
                    else bool(container.get(is_last_key, True))
                )
                if last_page:
                    break
                page_number += 1

            except (HTTPStatusError, ValueError, KeyError) as e:
                logger.error(f"Error paginating {endpoint}: {e}")
                break

    async def _send_cursor_paginated_request(
        self,
        endpoint: str,
        content_key: str,
        method: str,
        json_data: Optional[Dict[str, Any]],
        ignored_errors: Optional[List[IgnoredError]],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send cursor-based paginated API requests to the ArmorCode API."""
        after_key = None

        while True:
            try:
                params = {**self.DEFAULT_PARAMS}
                if after_key is not None:
                    params["afterKey"] = after_key

                response = await self.send_api_request(
                    endpoint,
                    method=method,
                    params=params,
                    json_data=json_data,
                    ignored_errors=ignored_errors,
                )

                container: Dict[str, Any] = (
                    response.get("data", {})
                    if isinstance(response.get("data"), dict)
                    else response
                )
                items = container.get(content_key, [])

                if not isinstance(items, list):
                    break

                if not items:
                    logger.info(f"No items returned for {endpoint}")
                    break

                logger.info(f"Fetched {len(items)} items from {endpoint}")
                yield items

                after_key = container.get("afterKey")
                if not after_key:
                    break

            except (HTTPStatusError, ValueError, KeyError) as e:
                logger.error(f"Error paginating {endpoint}: {e}")
                break

    async def send_paginated_request(
        self,
        endpoint: str,
        content_key: str = "content",
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        use_offset_pagination: bool = True,
        is_last_key: Optional[str] = "last",
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send paginated API requests to the ArmorCode API."""
        if use_offset_pagination:
            async for items in self._send_offset_paginated_request(
                endpoint, content_key, method, json_data, is_last_key, ignored_errors
            ):
                yield items
        else:
            async for items in self._send_cursor_paginated_request(
                endpoint, content_key, method, json_data, ignored_errors
            ):
                yield items
