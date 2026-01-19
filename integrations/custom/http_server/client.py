"""
Ocean Custom Client

Main client for making authenticated HTTP requests with automatic pagination support.
Uses Ocean's built-in HTTP client with caching and rate limiting.
"""

import asyncio
import functools
from typing import AsyncGenerator, List, Dict, Any, Optional
import httpx
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryTransport
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)

from http_server.handlers import get_auth_handler, get_pagination_handler
from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig


class HttpServerClient:
    """HTTP client with configurable authentication and pagination using Ocean's built-in mechanisms"""

    def __init__(
        self,
        base_url: str,
        auth_type: str,
        auth_config: Dict[str, Any],
        pagination_config: Dict[str, Any],
        verify_ssl: bool = True,
        max_concurrent_requests: int = 10,
        custom_headers: Optional[Dict[str, str]] = None,
        custom_auth_request: Optional[CustomAuthRequestConfig] = None,
        custom_auth_response: Optional[CustomAuthResponseConfig] = None,
        skip_setup: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_type = auth_type
        self.auth_config = auth_config
        self.pagination_config = pagination_config
        self.verify_ssl = verify_ssl
        self.custom_headers = custom_headers or {}

        # Use Ocean's built-in HTTP client with retry and rate limiting
        # Leverage Ocean's core client_timeout capability
        if not verify_ssl:
            logger.warning(
                "SSL verification is disabled - not recommended for production"
            )
        self.client = OceanAsyncClient(
            RetryTransport,
            timeout=ocean.config.client_timeout,
            verify=verify_ssl,
        )

        # Configure authentication using handler pattern
        self.auth_handler = get_auth_handler(
            self.auth_type,
            self.client,
            self.auth_config,
            custom_auth_request=custom_auth_request,
            custom_auth_response=custom_auth_response,
        )

        # Only call setup() if not skipping (for backward compatibility)
        # When skip_setup=True, authentication will be done via @ocean.on_start()
        if not skip_setup:
            self.auth_handler.setup()

        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def fetch_paginated_data(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch data with automatic rate limiting and concurrency control"""

        async def _fetch() -> AsyncGenerator[List[Dict[str, Any]], None]:
            async for batch in self._fetch_with_pagination(
                endpoint, method, query_params, headers, body
            ):
                yield batch

        async for batch in semaphore_async_iterator(self.semaphore, _fetch):
            yield batch

    async def _fetch_with_pagination(
        self,
        endpoint: str,
        method: str,
        query_params: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, str]],
        body: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch data with pagination handling using handler pattern"""

        base_url = self.base_url.rstrip("/")
        endpoint_path = endpoint.lstrip("/")

        # Validate - raise error if empty
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if not endpoint_path:
            raise ValueError("endpoint cannot be empty")

        url = f"{base_url}/{endpoint_path}"
        params = query_params or {}
        request_headers = headers or {}

        pagination_type = self.pagination_config.get("pagination_type", "none")

        logger.info(
            f"Fetching data from {method} {url} with pagination: {pagination_type}"
        )

        # Get pagination handler (leverages Ocean's HTTP client)
        handler = get_pagination_handler(
            pagination_type=pagination_type,
            client=self.client,
            config=self.pagination_config,
            extract_items_fn=self._extract_items_from_response,
            make_request_fn=self._make_request,
            get_nested_value_fn=self._get_nested_value,
        )

        async for batch in handler.fetch_all(
            url, method, params, request_headers, body
        ):
            yield batch

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Extract value from nested dict using dot notation (e.g., 'meta.after_cursor')"""
        keys = path.split(".")
        value: Any = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    async def _make_request(
        self,
        url: str,
        method: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
        body: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make HTTP request using Ocean's built-in client with retry and rate limiting.
        Automatically re-authenticates on 401 errors for custom auth."""
        merged_headers = {
            "User-Agent": "Port-Ocean-HTTP-Integration/1.0",
            **self.custom_headers,
            **headers,
        }

        # Apply custom auth token if available (evaluates templates in headers/queryParams/body)
        request_body = body
        if self.auth_type == "custom" and hasattr(
            self.auth_handler, "apply_auth_to_request"
        ):
            merged_headers, params, request_body = (
                await self.auth_handler.apply_auth_to_request(
                    merged_headers, params, request_body
                )
            )

        max_retries = 1  # Only retry once on 401
        retry_count = 0

        while retry_count <= max_retries:
            try:
                # Build request - include body if present
                if request_body:
                    response = await self.client.request(
                        method=method,
                        url=url,
                        params=params,
                        headers=merged_headers,
                        json=request_body,
                    )
                else:
                    response = await self.client.request(
                        method=method,
                        url=url,
                        params=params,
                        headers=merged_headers,
                    )

                # Check for 401 BEFORE raise_for_status() to intercept before RetryTransport retries
                if (
                    response.status_code == 401
                    and retry_count < max_retries
                    and self.auth_type == "custom"
                    and hasattr(self.auth_handler, "reauthenticate")
                ):
                    logger.info(
                        f"Received 401 Unauthorized for {method} {url}, attempting re-authentication"
                    )
                    try:
                        await self.auth_handler.reauthenticate()
                        # Re-apply auth token after re-authentication (evaluate templates again)
                        if hasattr(self.auth_handler, "apply_auth_to_request"):
                            merged_headers, params, request_body = (
                                await self.auth_handler.apply_auth_to_request(
                                    merged_headers, params, body
                                )
                            )
                        retry_count += 1
                        continue  # Retry the request with new token
                    except Exception as auth_error:
                        logger.error(f"Failed to re-authenticate: {str(auth_error)}")
                        response.raise_for_status()  # Raise the original 401 error
                        return response  # This won't be reached, but satisfies type checker

                # For all other cases, use normal error handling
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

        # This should never be reached, but satisfies type checker
        raise RuntimeError("Unexpected exit from retry loop")

    def _extract_items_from_response(self, data: Any) -> List[Dict[str, Any]]:
        """Extract items from API response for processing"""
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        return []

    async def fetch_multiple_endpoints(
        self,
        endpoints: List[str],
        method: str = "GET",
        query_params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch multiple endpoints in parallel with concurrency control"""

        tasks = [
            semaphore_async_iterator(
                self.semaphore,
                functools.partial(
                    self.fetch_paginated_data, endpoint, method, query_params, headers
                ),
            )
            for endpoint in endpoints
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch
