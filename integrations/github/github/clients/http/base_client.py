from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

import asyncio

import httpx
from httpx import Response

from loguru import logger

from github.helpers.utils import IgnoredError
from github.clients.rate_limiter.limiter import GitHubRateLimiter
from github.clients.rate_limiter.utils import GitHubRateLimiterConfig, RateLimitInfo
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry
from github.clients.http.client_retry_handler import (
    ClientRetryHandler,
    ClientRetryConfig,
)


if TYPE_CHECKING:
    from github.clients.auth.abstract_authenticator import (
        AbstractGitHubAuthenticator,
    )


class AbstractGithubClient(ABC):
    def __init__(
        self,
        github_host: str,
        authenticator: "AbstractGitHubAuthenticator",
        **kwargs: Any,
    ) -> None:
        self.github_host = github_host
        self.authenticator = authenticator
        self.kwargs = kwargs
        self.rate_limiter: GitHubRateLimiter = GitHubRateLimiterRegistry.get_limiter(
            host=github_host, config=self.rate_limiter_config
        )
        self._retry_handler = ClientRetryHandler(ClientRetryConfig())

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

    async def headers(self, **kwargs: Any) -> Dict[str, str]:
        """Build and return headers for GitHub API requests."""
        return (await self.authenticator.get_headers(**kwargs)).as_dict()

    @property
    @abstractmethod
    def base_url(self) -> str: ...

    @property
    @abstractmethod
    def rate_limiter_config(self) -> GitHubRateLimiterConfig: ...

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        resource: str,
        method: str,
        ignored_errors: Optional[List[IgnoredError]] = None,
        ignore_default_errors: bool = True,
    ) -> bool:
        all_ignored_errors = (ignored_errors or []) + (
            self._DEFAULT_IGNORED_ERRORS if ignore_default_errors else []
        )
        status_code = error.response.status_code

        for ignored_error in all_ignored_errors:
            if str(status_code) == str(ignored_error.status):
                logger.warning(
                    f"Failed to {method} resources at {resource} due to {ignored_error.message} with status code {status_code}"
                )
                return True
        return False

    async def make_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        ignored_errors: Optional[List[IgnoredError]] = None,
        ignore_default_errors: bool = True,
        authenticator_headers_params: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Make a request to the GitHub API with retries, rate limiting and error handling.

        The retry loop runs *outside* the rate-limiter semaphore so that
        back-off sleeps (token refresh, rate-limit resets) do not block other
        coroutines from making progress.
        """
        handler = self._retry_handler
        last_error: Optional[httpx.HTTPStatusError] = None

        for attempt in range(handler.config.max_attempts):
            try:
                return await self._send_single_request(
                    resource=resource,
                    params=params,
                    method=method,
                    json_data=json_data,
                    authenticator_headers_params=authenticator_headers_params,
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                is_last_attempt = attempt >= handler.config.max_attempts - 1

                if (
                    handler.is_retryable(e.response, self.rate_limiter)
                    and not is_last_attempt
                ):
                    handler.prepare_retry(
                        e.response, self.authenticator, attempt, resource
                    )
                    sleep_time = handler.calculate_sleep(attempt, e.response)
                    logger.info(
                        f"[GitHubClient] sleeping {sleep_time:.1f}s before retry "
                        f"{attempt + 2}/{handler.config.max_attempts} for {method} {resource}"
                    )
                    await asyncio.sleep(sleep_time)
                    continue

                if self.rate_limiter.is_rate_limit_response(e.response):
                    raise

                if self._should_ignore_error(
                    e, resource, method, ignored_errors, ignore_default_errors
                ):
                    return Response(200, content=b"{}")
                raise

        raise last_error  # type: ignore[misc]

    async def _send_single_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]],
        method: str,
        json_data: Optional[Dict[str, Any]],
        authenticator_headers_params: Optional[Dict[str, Any]],
    ) -> Response:
        """Execute one request inside the rate-limiter semaphore."""
        async with self.rate_limiter:
            try:
                response = await self.authenticator.client.request(
                    method=method,
                    url=resource,
                    params=params,
                    json=json_data,
                    headers=await self.headers(**(authenticator_headers_params or {})),
                )
                response.raise_for_status()
                logger.debug(f"Successfully fetched {method} {resource}")
                return response

            except httpx.HTTPStatusError:
                raise

            except httpx.HTTPError as e:
                logger.error(
                    f"[GitHubClient] non-status HTTP error for {method} {resource}: "
                    f"{type(e).__name__} - {e}"
                )
                raise

            finally:
                if "response" in locals():
                    self.rate_limiter.update_rate_limits(response.headers, resource)

    async def send_api_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        ignored_errors: Optional[List[IgnoredError]] = None,
        ignore_default_errors: bool = True,
        authenticator_headers_params: Optional[Dict[str, Any]] = {},
    ) -> Dict[str, Any]:
        """Send request to GitHub API with error handling and rate limiting."""

        response = await self.make_request(
            resource,
            params,
            method,
            json_data,
            ignored_errors,
            ignore_default_errors,
            authenticator_headers_params,
        )
        return response.json()

    def get_rate_limit_status(self) -> Optional[RateLimitInfo]:
        """Get current rate limit status for monitoring."""
        return self.rate_limiter.rate_limit_info

    @abstractmethod
    def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send a paginated request to GitHub API and yield results."""
        pass
