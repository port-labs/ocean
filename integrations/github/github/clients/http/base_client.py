from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

import httpx
from httpx import Response

from loguru import logger

from github.helpers.utils import IgnoredError
from github.clients.rate_limiter.limiter import GitHubRateLimiter
from github.clients.rate_limiter.utils import GitHubRateLimiterConfig, RateLimitInfo
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry


if TYPE_CHECKING:
    from github.clients.auth.abstract_authenticator import (
        AbstractGitHubAuthenticator,
    )


class AbstractGithubClient(ABC):
    def __init__(
        self,
        organization: str,
        github_host: str,
        authenticator: "AbstractGitHubAuthenticator",
        **kwargs: Any,
    ) -> None:
        self.organization = organization
        self.github_host = github_host
        self.authenticator = authenticator
        self.kwargs = kwargs
        self.rate_limiter: GitHubRateLimiter = GitHubRateLimiterRegistry.get_limiter(
            host=github_host, config=self.rate_limiter_config
        )

    _DEFAULT_IGNORED_ERRORS = [
        IgnoredError(
            status=401,
            message="Unauthorized access to endpoint — authentication required or token invalid",
            type="UNAUTHORIZED",
        ),
        # Note: While GitHub documentation mentions 403 as a rate limit code,
        # in practice 403s are tied to permissions rather than rate limiting.
        # Therefore we ignore 403s rather than retrying them as we do for rate limit errors.
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

    @property
    async def headers(self) -> Dict[str, str]:
        """Build and return headers for GitHub API requests."""
        return (await self.authenticator.get_headers()).as_dict()

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

    async def make_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> Response:
        """Make a request to the GitHub API with GitHub rate limiting and error handling."""

        async with self.rate_limiter:
            try:
                response = await self.authenticator.client.request(
                    method=method,
                    url=resource,
                    params=params,
                    json=json_data,
                    headers=await self.headers,
                )
                response.raise_for_status()

                logger.debug(f"Successfully fetched {method} {resource}")
                return response

            except httpx.HTTPStatusError as e:
                response = e.response

                if not self.rate_limiter.is_rate_limit_response(response):
                    if self._should_ignore_error(e, resource, ignored_errors):
                        return Response(200, content=b"{}")

                logger.error(
                    f"GitHub API error for endpoint '{resource}': Status {response.status_code}, "
                    f"Method: {method}, Response: {response.text}"
                )

                raise

            except httpx.HTTPError as e:
                logger.error(f"HTTP error for endpoint '{resource}': {str(e)}")
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
    ) -> Dict[str, Any]:
        """Send request to GitHub API with error handling and rate limiting."""

        response = await self.make_request(
            resource, params, method, json_data, ignored_errors
        )
        return response.json()

    def get_rate_limit_status(self) -> Optional[RateLimitInfo]:
        """Get current rate limit status for monitoring."""
        return self.rate_limiter.rate_limit_info

    def log_rate_limit_status(self) -> None:
        """Log current rate limit status for debugging."""
        self.rate_limiter.log_rate_limit_status()

    @abstractmethod
    def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send a paginated request to GitHub API and yield results.

        Args:
            resource: The API resource path
            params: Query parameters or variables
            method: HTTP method

        Yields:
            Lists of items from paginated responses
        """
        pass
