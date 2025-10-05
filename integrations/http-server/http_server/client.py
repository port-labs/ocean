"""
HTTP Server Client

Main client for making authenticated HTTP requests with automatic pagination support.
Uses Ocean's built-in HTTP client with caching and rate limiting.
"""

import asyncio
import functools
from typing import AsyncGenerator, List, Dict, Any, Optional
from urllib.parse import urljoin
import httpx
from loguru import logger

from port_ocean.utils.async_http import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)


class HttpServerClient:
    """HTTP client with configurable authentication and pagination using Ocean's built-in mechanisms"""

    def __init__(
        self,
        base_url: str,
        auth_type: str,
        auth_config: Dict[str, Any],
        pagination_config: Dict[str, Any],
        timeout: int = 30,
        verify_ssl: bool = True,
        max_concurrent_requests: int = 10,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_type = auth_type
        self.auth_config = auth_config
        self.pagination_config = pagination_config
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        # Use Ocean's built-in HTTP client (has retry/rate limiting built-in)
        self.client = http_async_client

        # Configure authentication
        self._setup_auth()

        # Simple concurrency control (like other Ocean integrations)
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

    def _setup_auth(self):
        """Setup authentication following Ocean patterns"""
        # Set User-Agent
        self.client.headers["User-Agent"] = "Port-Ocean-HTTP-Integration/1.0"

        # Configure authentication
        if self.auth_type == "bearer_token":
            token = self.auth_config.get("api_token")
            if token:
                self.client.headers["Authorization"] = f"Bearer {token}"

        elif self.auth_type == "api_key":
            api_key = self.auth_config.get("api_key")
            key_header = self.auth_config.get("api_key_header", "X-API-Key")
            if api_key and key_header:
                self.client.headers[key_header] = api_key

        elif self.auth_type == "basic":
            username = self.auth_config.get("username")
            password = self.auth_config.get("password")
            if username and password:
                self.client.auth = httpx.BasicAuth(username, password)

    @cache_iterator_result()  # Ocean handles caching automatically!
    async def fetch_paginated_data(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch data with automatic caching and rate limiting"""

        # Use Ocean's semaphore for concurrency control
        async def _fetch():
            async for batch in self._fetch_with_pagination(
                endpoint, method, query_params, headers
            ):
                yield batch

        # Ocean's semaphore controls concurrency
        async for batch in semaphore_async_iterator(self.semaphore, _fetch):
            yield batch

    async def _fetch_with_pagination(
        self,
        endpoint: str,
        method: str,
        query_params: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, str]],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch data with pagination handling"""

        url = urljoin(self.base_url, endpoint.lstrip("/"))
        params = query_params or {}
        request_headers = headers or {}

        pagination_type = self.pagination_config.get("pagination_type", "none")

        logger.info(
            f"Fetching data from {method} {url} with pagination: {pagination_type}"
        )

        if pagination_type == "none":
            # Single request, no pagination
            async for batch in self._fetch_single_page(
                url, method, params, request_headers
            ):
                yield batch

        elif pagination_type == "offset":
            async for batch in self._fetch_offset_paginated(
                url, method, params, request_headers
            ):
                yield batch

        elif pagination_type == "page":
            async for batch in self._fetch_page_paginated(
                url, method, params, request_headers
            ):
                yield batch

        elif pagination_type == "cursor":
            async for batch in self._fetch_cursor_paginated(
                url, method, params, request_headers
            ):
                yield batch

        else:
            logger.warning(
                f"Unknown pagination type: {pagination_type}, falling back to single request"
            )
            async for batch in self._fetch_single_page(
                url, method, params, request_headers
            ):
                yield batch

    async def _fetch_single_page(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch single page without pagination"""
        response = await self._make_request(url, method, params, headers)
        items = self._extract_items_from_response(response.json())
        if items:
            yield items

    async def _fetch_offset_paginated(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch data using offset/limit pagination"""
        page_size = self.pagination_config.get("page_size", 100)
        offset_param = self.pagination_config.get("offset_param", "offset")
        limit_param = self.pagination_config.get("limit_param", "limit")

        offset = 0

        while True:
            current_params = {
                **params,
                offset_param: offset,
                limit_param: page_size,
            }

            response = await self._make_request(url, method, current_params, headers)
            response_data = response.json()
            items = self._extract_items_from_response(response_data)

            if not items:
                break

            yield items

            # Check if we have more data
            if len(items) < page_size:
                break

            # Check pagination metadata if available
            pagination_info = self._extract_pagination_info(response_data)
            if pagination_info and not pagination_info.get("has_more", True):
                break

            offset += page_size

    async def _fetch_page_paginated(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch data using page/size pagination"""
        page_size = self.pagination_config.get("page_size", 100)
        page_param = self.pagination_config.get("page_param", "page")
        size_param = self.pagination_config.get("size_param", "size")
        start_page = self.pagination_config.get("start_page", 1)

        page = start_page

        while True:
            current_params = {
                **params,
                page_param: page,
                size_param: page_size,
            }

            response = await self._make_request(url, method, current_params, headers)
            response_data = response.json()
            items = self._extract_items_from_response(response_data)

            if not items:
                break

            yield items

            # Check if we have more data
            if len(items) < page_size:
                break

            # Check pagination metadata if available
            pagination_info = self._extract_pagination_info(response_data)
            if pagination_info:
                if not pagination_info.get("has_next", True):
                    break
                # Some APIs provide total_pages
                total_pages = pagination_info.get("total_pages")
                if total_pages and page >= total_pages:
                    break

            page += 1

    async def _fetch_cursor_paginated(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch data using cursor-based pagination"""
        page_size = self.pagination_config.get("page_size", 100)
        cursor_param = self.pagination_config.get("cursor_param", "cursor")
        limit_param = self.pagination_config.get("limit_param", "limit")

        cursor = None

        while True:
            current_params = {**params, limit_param: page_size}

            if cursor:
                current_params[cursor_param] = cursor

            response = await self._make_request(url, method, current_params, headers)
            response_data = response.json()
            items = self._extract_items_from_response(response_data)

            if not items:
                break

            yield items

            # Get next cursor from response
            pagination_info = self._extract_pagination_info(response_data)
            if not pagination_info:
                break

            next_cursor = pagination_info.get("next_cursor")
            has_more = pagination_info.get("has_more", False)

            if not next_cursor or not has_more:
                break

            cursor = next_cursor

    async def _make_request(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> httpx.Response:
        """Make HTTP request using Ocean's built-in client (has retry/rate limiting)"""
        try:
            # Use Ocean's HTTP client - it already handles retry and rate limiting!
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error {e.response.status_code} for {method} {url}: {e.response.text}"
            )
            raise

        except httpx.RequestError as e:
            logger.error(f"Request error for {method} {url}: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error for {method} {url}: {str(e)}")
            raise

    def _extract_items_from_response(self, data: Any) -> List[Dict[str, Any]]:
        """Extract items from API response - returns raw response for Ocean to process"""
        # Ocean framework will handle items_to_parse, so just return the raw response
        # Ocean expects the raw response and will apply items_to_parse JQ expression
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]  # Return as single item, Ocean will handle extraction
        return []

    def _extract_pagination_info(self, data: Any) -> Optional[Dict[str, Any]]:
        """Extract pagination information from response"""
        if not isinstance(data, dict):
            return None

        # Try common pagination keys
        for key in ["pagination", "meta", "paging", "page_info"]:
            if key in data:
                return data[key]

        return None

    async def fetch_multiple_endpoints(
        self,
        endpoints: List[str],
        method: str = "GET",
        query_params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch multiple endpoints in parallel following Ocean patterns (like AWS integration)"""

        # Create tasks for each endpoint
        tasks = [
            semaphore_async_iterator(
                self.semaphore,
                functools.partial(
                    self.fetch_paginated_data, endpoint, method, query_params, headers
                ),
            )
            for endpoint in endpoints
        ]

        # Stream results as they become available
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch

    # Note: No need to close Ocean's singleton HTTP client
    # It's managed by Ocean and shared across all events
