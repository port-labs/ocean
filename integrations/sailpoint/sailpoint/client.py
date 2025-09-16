from typing import Any, Callable, Dict, Optional
from sailpoint.utils.logging import Logger, LoggerProtocol
from sailpoint.connector import SailPointAuthManager
from sailpoint.utils.pagination import PaginatorProtocol, LimitOffsetPagination
from sailpoint.utils.commons import paginated_response, benchmark_latency
from sailpoint.utils.rules import (
    RateLimitError,
    exponential_backoff_retry,
    SAILPOINT_LIMITER as SAILPOINT_RATE_LIMITER,
)
from port_ocean.utils.async_http import http_async_client
from port_ocean.log.sensetive import sensitive_log_filter
from sailpoint.exceptions import ThirdPartyAPIError, SailPointAuthError
from port_ocean.utils.async_iterators import semaphore_async_iterator


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

        if api_version:
            self._api_version = api_version

    async def _get_headers(self) -> Dict[str, str]:
        token_info = await self._auth_client.get_valid_token()
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
            await self._exception_handler(
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

        raise error

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
