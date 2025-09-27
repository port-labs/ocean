from enum import StrEnum
import asyncio
from typing import Any, Callable, Dict, Optional, AsyncGenerator
from sailpoint.utils.logging import Logger, LoggerProtocol
from sailpoint.connector import SailPointAuthManager, TokenInfo
from sailpoint.utils.pagination import PaginatorProtocol, LimitOffsetPagination
from sailpoint.utils.commons import paginated_response, benchmark_latency
from sailpoint.utils.rules import (
    RateLimitError,
    exponential_backoff_retry,
    SAILPOINT_LIMITER as SAILPOINT_RATE_LIMITER,
)
from sailpoint.utils.rules import TransientError
from sailpoint.utils.commons import paginated_response
from port_ocean.utils.cache import cache_coroutine_result, cache_iterator_result
from port_ocean.utils.async_http import http_async_client
from port_ocean.log.sensetive import sensitive_log_filter
from sailpoint.exceptions import ThirdPartyAPIError, SailPointAuthError
from port_ocean.utils.async_iterators import semaphore_async_iterator


CLIENT_TIMEOUT = 60


class ResourceKey(StrEnum):
    # Resource kinds in SailPoint IdentityNow
    IDENTITY = "identity"
    ACCOUNT = "account"
    ENTITLEMENT = "entitlement"
    ACCESS_PROFILE = "accessProfile"
    ROLE = "role"
    SOURCE = "source"


class SailpointClient:
    """
    Client for interacting with the SailPoint IdentityNow API

    (https://developer.sailpoint.com/docs/identitynow/).

    Uses:
    - OAuth2 for authentication
    - Async HTTP requests for efficient API calls
    - Handles token refresh and error scenarios

    Supports:
    - Fetching user details
    - Managing identities
    - Accessing and modifying access profiles
    - Handling entitlements and roles
    - Working with governance and compliance

    What it does not do:
    - Directly manage OAuth2 tokens (handled by our SailPointAuthManager)
    - Synchronous API calls (all calls are async)
    - Detailed error handling for specific API endpoints (general error handling is provided)

    Delegates:
    - Authentication to SailPointAuthManager:
    - Logging to our Logger utility
    - Pagination to our Paginator Protocol, such that we can compose with
      different pagination strategies

    """

    def __init__(
        self,
        auth_client: SailPointAuthManager,
        api_headers: Optional[Dict[str, str]] = None,
        api_version: Optional[str] = None,
        paginator: PaginatorProtocol = LimitOffsetPagination(),
    ) -> None:
        self._auth_client = auth_client
        self._base_url = auth_client._base_url
        self._api_headers = api_headers or {}
        self._api_version = auth_client.SAILPOINT_DEFAULT_API_VERSION
        self._http_client = http_async_client
        self.logger = Logger
        self.paginator = paginator
        self._http_client.timeout = CLIENT_TIMEOUT

        if api_version:
            self._api_version = api_version

    async def _get_headers(self) -> Dict[str, str]:
        token_info: TokenInfo = await self._auth_client.get_valid_token()
        return {"Authorization": f"Bearer {token_info.access_token}"}

    async def send_request(
        self,
        func: Callable,
        logger: LoggerProtocol,
        method: str,
        endpoint: str,
        *args,
        **kwargs,
    ):
        """
        Sends an HTTP request using the provided function, with logging and error handling.

        Each request is rate-limited using the SAILPOINT_RATE_LIMITER to avoid exceeding API limits.

        Usage:
            NOTE: `endpoint` should be a relative path, e.g. 'users/{user_id}'
        """
        await SAILPOINT_RATE_LIMITER.acquire()
        try:
            return await exponential_backoff_retry(
                func, method=method, endpoint=endpoint, *args, logger=logger, **kwargs
            )
        except Exception as e:
            raise await self._exception_handler(
                e, logger, context={"endpoint": endpoint, "method": method}
            )

    async def _exception_handler(
        self,
        error: Exception,
        logger: LoggerProtocol,
        context: dict,
    ):
        if isinstance(error, (ThirdPartyAPIError, SailPointAuthError)):
            logger.log_error(message="Fatal API error", error=error, context=context)
        elif isinstance(error, RateLimitError):
            logger.log_error(
                message="Rate limit exceeded after retries",
                error=error,
                context=context,
            )
        else:
            logger.log_error(message="Unexpected error", error=error, context=context)

        return error

    async def _send_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        url = f"{self._base_url}/{self._api_version}/{endpoint.lstrip('/')}"
        auth_headers = await self._get_headers()
        all_headers = {**self._api_headers, **(headers or {}), **auth_headers}

        sensitive_log_filter.hide_sensitive_strings(
            *(list(all_headers.values()) + [str(data), str(json)])
        )

        async with self._http_client as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json,
                headers=all_headers,
            )

            if response.status_code == 403:
                raise SailPointAuthError(
                    "Forbidden access - you do not have permission to access this resource",
                    response.status_code,
                )
            if response.status_code == 401:
                raise SailPointAuthError(
                    "Unauthorized access - invalid token",
                    response.status_code,
                )

            if response.status_code == 419:
                raise SailPointAuthError(
                    "Token expired - please refresh your token",
                    response.status_code,
                )

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After"))
                raise RateLimitError(
                    message="Rate limit exceeded - too many requests",
                    retry_after=retry_after,
                )

            if response.status_code >= 400:
                raise ThirdPartyAPIError(
                    f"API request failed with status {response.status_code}: {response.text}",
                    response.status_code,
                )

            if response.status_code == 204:
                return None

        return response

    @benchmark_latency
    async def _get_single_resource(
        self,
        resource: ResourceKey,
        resource_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        endpoint = f"{resource.value}s/{resource_id}"
        response = await self.send_request(
            self._send_request,
            self.logger,  # type: ignore[arg-type]
            method="GET",
            endpoint=endpoint,
            params=params,
        )
        return await response.json()

    async def _fetch_paginated_resources(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[list[Dict[str, Any]], None]:
        """
        Fetch and yield all items across paginated responses
        for a given SailPoint API endpoint using the configured paginator
        """
        current_params = {**(params or {}), **self.paginator.get_query_params()}

        while True:
            response = await self._send_request("GET", endpoint, params=current_params)

            page = await paginated_response(paginator=self.paginator, response=response)

            yield page["results"]  # type: ignore[index]

            # if there are more pages, if we should continue other wise, break
            if not self.paginator.has_more(len(page["results"])):  # type: ignore[arg-type]
                break

            # advance and update params
            self.paginator.advance()
            current_params = {**(params or {}), **self.paginator.get_query_params()}

    async def get_all_resources(
        self,
        resource: ResourceKey,
        params: Optional[Dict[str, Any]] = None,
        max_concurrency: int = 5,
    ) -> AsyncGenerator[list[Dict[str, Any]], None]:
        """
        Fetches all resources of a given type, handling pagination and concurrency.

        This is a convenience method that abstracts away of doing repetitive work. For context here,
        SailPoint's API paginates results, so this method will handle fetching all pages of results
        for the specified resource type using our paginated_response.

        Usage:
        Call this method like so to get all identities (for example):

            ```python
            async for identity in client.get_all_resources(ResourceKey.IDENTITY):
                print(identity) or print(identity['id'])
            ```

            You can also perform batch operation on various resource types by combining
            this with the `stream_async_iterators_tasks` from Port's library as below:

            ```python
            from port_ocean.utils.async_iterators import stream_async_iterators_tasks

            async def process_all(client: SailpointClient):
                async for resource in stream_async_iterators_tasks(
                    client.get_all_resources(ResourceKey.IDENTITY),
                    client.get_all_resources(ResourceKey.ROLE),
                    client.get_all_resources(ResourceKey.SOURCE),
                ):
                    print(f"Fetched {resource['id']} ({resource['type']})")
            ```

            To control or limit the number of concurrent requests made to the SailPoint API,
            you should adjust the `max_concurrency` parameter. This parameter sets the maximum number
            of concurrent requests that can be made at any given time. For example, if you set

            ```python
            async for entitlement in client.get_all_resources(ResourceKey.ENTITLEMENT, max_concurrency=3):
                print(entitlement["name"])
            ```

        Args:
            resource (ResourceKey): The type of resource to fetch.
            params (Optional[Dict[str, Any]]): Query parameters for the request.
            max_concurrency (int): Maximum number of concurrent requests.


        Yields:
            AsyncGenerator[Dict[str, Any], None]: An async generator yielding resource items.
        """
        endpoint = f"{resource.value}"

        if resource.value == ResourceKey.ACCESS_PROFILE:
            endpoint = "access-profile"

        fetch_func = lambda: self._fetch_paginated_resources(endpoint, params=params)

        async for paginated_result in semaphore_async_iterator(
            asyncio.BoundedSemaphore(max_concurrency),
            fetch_func,
        ):
            yield paginated_result
