import time
import asyncio
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass
import httpx
from loguru import logger
from github.helpers.exceptions import RateLimitExceededError


@dataclass
class RateLimitInfo:
    """GitHub rate limit information from response headers."""

    remaining: int
    reset_time: int
    limit: int

    @property
    def seconds_until_reset(self) -> int:
        return max(0, self.reset_time - int(time.time()))


class GitHubRateLimiter:
    """
    GitHub API Rate Limiter

    Handles GitHub's rate limiting by parsing response headers and implementing
    appropriate backoff strategies.

    GitHub Rate Limits:
    - Core: 5,000 requests/hour for authenticated users (varies by auth type)
    - Search: 30 requests/minute for authenticated users
    - GraphQL: 5,000 requests/hour for authenticated users
    - Secondary: 100 concurrent requests, 900 points/minute for REST, etc.

    Headers Parsed:
    - X-RateLimit-Limit: Total requests allowed per hour
    - X-RateLimit-Remaining: Requests remaining in current window
    - X-RateLimit-Reset: Unix timestamp when rate limit resets
    - Retry-After: Seconds to wait (for secondary rate limits)
    """

    def __init__(self, max_retries: int = 5, max_concurrent: int = 10):
        self.max_retries = max_retries
        self._rate_limits: Dict[str, RateLimitInfo] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def _determine_resource_type(self, resource: str) -> str:
        """
        Determine the rate limit resource type based on the API endpoint.

        Args:
            resource: Full API URL (e.g., "https://api.github.com/search/repositories", "/graphql")

        Returns:
            Resource type string (core, search, graphql, etc.)
        """
        if "/search/" in resource:
            return "search"
        elif resource.endswith("/graphql"):
            return "graphql"
        else:
            return "core"

    def _parse_rate_limit_headers(
        self, response: httpx.Response
    ) -> Optional[RateLimitInfo]:
        """
        Parse GitHub's rate limit headers from response.

        GitHub sends these headers with every API response:
        - X-RateLimit-Limit: Total requests allowed per hour
        - X-RateLimit-Remaining: Requests remaining in current window
        - X-RateLimit-Reset: Unix timestamp when rate limit resets

        Returns RateLimitInfo if headers are present, None otherwise.
        """
        required_headers = [
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
        ]
        if all(header in response.headers for header in required_headers):
            return RateLimitInfo(
                limit=int(response.headers["x-ratelimit-limit"]),
                remaining=int(response.headers["x-ratelimit-remaining"]),
                reset_time=int(response.headers["x-ratelimit-reset"]),
            )
        return None

    def _get_backoff_time(self, response: httpx.Response) -> Optional[float]:
        """
        Calculate backoff time based on GitHub's rate limit headers.

        This implements GitHub's recommended backoff strategy:
        1. For secondary rate limits (429): Use Retry-After header
        2. For primary rate limits (403): Calculate time until X-RateLimit-Reset
        3. Minimum backoff: 60 seconds to prevent aggressive retries

        Args:
            response: HTTP response from GitHub API

        Returns:
            Seconds to wait before retrying, or None if no backoff needed
        """
        min_backoff_time = 60.0

        # Secondary rate limits (429 Too Many Requests)
        # GitHub sends Retry-After header with exact seconds to wait
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            return max(float(retry_after), min_backoff_time)

        # Primary rate limits (403 Forbidden)
        # Calculate time until rate limit window resets
        reset_time = response.headers.get("X-RateLimit-Reset")
        if reset_time:
            backoff_time = max(float(reset_time) - time.time(), min_backoff_time)
            return backoff_time

        return None

    def _handle_rate_limit_error(
        self, response: httpx.Response, resource: str, resource_type: str
    ) -> Optional[float]:
        """
        Handle rate limit errors and return backoff time if retry is needed.

        Args:
            response: HTTP response that might be a rate limit error
            resource: Resource identifier for logging
            resource_type: Type of resource (core, search, graphql, etc.)

        Returns:
            Backoff time in seconds if this is a rate limit error, None otherwise
        """
        if response.status_code in [403, 429]:
            backoff_time = self._get_backoff_time(response)
            if backoff_time:
                logger.warning(
                    f"Rate limit hit for {resource} ({resource_type}). "
                    f"Status: {response.status_code}. "
                    f"Waiting {backoff_time:.1f} seconds."
                )
                return backoff_time
        return None

    async def execute_request(
        self,
        request_func: Callable[..., Awaitable[httpx.Response]],
        resource: str,
        *args: Any,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Execute a request with GitHub rate limiting and retry logic.

        This method wraps any async request function and adds:
        1. Concurrency control with semaphore
        2. Automatic rate limit detection
        3. Smart backoff based on GitHub's headers
        4. Retry logic for rate limit errors
        5. Exponential backoff for other errors

        Args:
            request_func: Async function that makes the HTTP request
            resource: Resource identifier for logging
            *args, **kwargs: Arguments passed to request_func

        Returns:
            HTTP response from the request

        Raises:
            httpx.HTTPStatusError: If rate limit exceeded after max retries
        """

        async with self._semaphore:
            retry_count = 0
            resource_type = self._determine_resource_type(resource)

            while retry_count <= self.max_retries:
                try:
                    response = await request_func(resource, *args, **kwargs)

                    rate_limit_info = self._parse_rate_limit_headers(response)
                    if rate_limit_info:
                        self._rate_limits[resource_type] = rate_limit_info
                        logger.debug(
                            f"Rate limit info for {resource_type}: "
                            f"{rate_limit_info.remaining}/{rate_limit_info.limit} remaining"
                        )

                    backoff_time = self._handle_rate_limit_error(
                        response, resource, resource_type
                    )
                    if backoff_time:
                        await asyncio.sleep(backoff_time)
                        retry_count += 1
                        continue

                    return response

                except httpx.HTTPStatusError as e:
                    backoff_time = self._handle_rate_limit_error(
                        e.response, resource, resource_type
                    )
                    if backoff_time:
                        await asyncio.sleep(backoff_time)
                        retry_count += 1
                        continue

                    raise

                except Exception as e:
                    if retry_count < self.max_retries:
                        delay = min(60, 2**retry_count)
                        logger.debug(
                            f"Request failed for {resource}: {e}. "
                            f"Retrying in {delay}s (attempt {retry_count + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(delay)
                        retry_count += 1
                        continue
                    else:
                        logger.error(
                            f"Request failed for {resource} after {self.max_retries} retries: {e}"
                        )
                        raise

            # If we get here, we've exhausted all retries
            raise RateLimitExceededError(resource, self.max_retries)

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status for monitoring.

        Returns:
            Dictionary with rate limit information including:
            - limit: Total requests allowed per hour
            - remaining: Requests remaining in current window
            - reset_time: Unix timestamp when rate limit resets
            - seconds_until_reset: Seconds until rate limit resets
            - utilization_percentage: Percentage of rate limit used
        """
        status = {}

        for resource, rate_limit in self._rate_limits.items():
            status[resource] = {
                "limit": rate_limit.limit,
                "remaining": rate_limit.remaining,
                "reset_time": rate_limit.reset_time,
                "seconds_until_reset": rate_limit.seconds_until_reset,
                "utilization_percentage": (
                    (rate_limit.limit - rate_limit.remaining) / rate_limit.limit
                )
                * 100,
            }

        return status

    def log_rate_limit_status(self) -> None:
        """
        Log current rate limit status for debugging.

        Example output:
        DEBUG: core: 4500/5000 remaining (10.0% used) - resets in 1800s
        DEBUG: search: 25/30 remaining (16.7% used) - resets in 45s
        DEBUG: graphql: 4995/5000 remaining (0.1% used) - resets in 3600s
        """
        status = self.get_rate_limit_status()

        for resource, info in status.items():
            logger.debug(
                f"{resource}: {info['remaining']}/{info['limit']} remaining "
                f"({info['utilization_percentage']:.1f}% used) - "
                f"resets in {info['seconds_until_reset']}s"
            )
