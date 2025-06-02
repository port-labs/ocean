import asyncio
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime, timezone

import aiolimiter
from loguru import logger

if TYPE_CHECKING:
    from github.clients.github_client import GitHubClient


class BasicGitHubRateLimiter:
    """
    A basic GitHub API rate limiter.

    - Uses GitHub's /rate_limit endpoint.
    - Calls the endpoint once before the reset time if approaching the limit.
    - Uses aiolimiter for a general request interval.
    """

    MIN_REQUEST_INTERVAL = 0.1  # Minimum seconds between any two requests
    CORE_API_THRESHOLD = (
        50  # Number of remaining requests to trigger a rate_limit check
    )
    # (set higher in practice, e.g., 100-500, depending on burst needs)

    def __init__(self) -> None:
        self.general_limiter = aiolimiter.AsyncLimiter(
            max_rate=1 / self.MIN_REQUEST_INTERVAL, time_period=1
        )
        self.core_api_status: Optional[Dict[str, Any]] = None
        self._lock = asyncio.Lock()
        self._checked_this_reset_period = False
        self._last_reset_time: Optional[datetime] = None

        logger.info(
            f"BasicGitHubRateLimiter initialized. Min interval: {self.MIN_REQUEST_INTERVAL}s, "
            f"Core API threshold: {self.CORE_API_THRESHOLD}"
        )

    async def _should_check_rate_limit_endpoint(self) -> bool:
        """Determines if we need to call the /rate_limit endpoint."""
        if not self.core_api_status:
            return True  # No status yet, good to check

        if self._checked_this_reset_period:
            return False  # Already checked in the current window

        remaining = self.core_api_status.get("remaining")
        if remaining is not None and remaining < self.CORE_API_THRESHOLD:
            logger.debug(
                f"Remaining core API calls ({remaining}) below threshold ({self.CORE_API_THRESHOLD}). "
                f"Will check /rate_limit endpoint."
            )
            return True
        return False

    async def _refresh_rate_limit_status(self, github_client: "GitHubClient") -> None:
        """Refreshes rate limit status from GitHub's /rate_limit endpoint."""
        logger.debug("Attempting to refresh GitHub rate limit status.")
        try:
            # This is a conceptual call; github_client needs a method to get this.
            # We are making an actual API call here, which itself is not rate-limited by this limiter.
            rate_limit_data = await github_client.fetch_rate_limit_from_endpoint()
            if rate_limit_data and "core" in rate_limit_data:
                self.core_api_status = rate_limit_data["core"]
                self._checked_this_reset_period = (
                    True  # Mark as checked for this period
                )

                reset_timestamp = self.core_api_status.get("reset")
                if reset_timestamp:
                    self._last_reset_time = datetime.fromtimestamp(
                        reset_timestamp, timezone.utc
                    )

                logger.info(
                    f"GitHub rate limit status refreshed. "
                    f"Core: {self.core_api_status.get('remaining')}/{self.core_api_status.get('limit')}. "
                    f"Resets at: {self._last_reset_time}"
                )
            else:
                logger.warning("Failed to parse 'core' data from /rate_limit response.")

        except Exception as e:
            logger.error(f"Failed to refresh GitHub rate limit status: {e}")
            # Optionally, implement retry or backoff for this refresh itself

    async def acquire(self, github_client: "GitHubClient") -> None:
        """Acquires permission to make a GitHub API request."""
        async with self._lock:
            await self.general_limiter.acquire()  # General politeness delay

            now_utc = datetime.now(timezone.utc)
            if self._last_reset_time and now_utc >= self._last_reset_time:
                logger.debug(
                    f"Reset time {self._last_reset_time} has passed. Resetting check flag."
                )
                self._checked_this_reset_period = False  # Reset period has passed
                self.core_api_status = None  # Invalidate old status

            if await self._should_check_rate_limit_endpoint():
                await self._refresh_rate_limit_status(github_client)

            # After potentially refreshing, check if we need to wait
            if self.core_api_status:
                remaining = self.core_api_status.get("remaining")
                reset_timestamp = self.core_api_status.get("reset")

                if remaining is not None and reset_timestamp is not None:
                    if remaining < self.CORE_API_THRESHOLD:  # Check again after refresh
                        reset_time = datetime.fromtimestamp(
                            reset_timestamp, timezone.utc
                        )
                        if now_utc < reset_time:
                            wait_seconds = (reset_time - now_utc).total_seconds()
                            if wait_seconds > 0:
                                logger.warning(
                                    f"Core API limit approaching ({remaining} remaining). "
                                    f"Waiting for {wait_seconds:.2f}s until {reset_time}."
                                )
                                await asyncio.sleep(wait_seconds)
                                # After waiting, the period has reset, so reset the flag
                                self._checked_this_reset_period = False
                                self.core_api_status = None  # Invalidate status
                        else:
                            # Reset time is in the past, meaning we should be clear or refresh again
                            self._checked_this_reset_period = False
                            self.core_api_status = None

    def update_from_headers(self, headers: Dict[str, str]) -> None:
        """Updates rate limit status from response headers."""
        try:
            remaining = headers.get("x-ratelimit-remaining")
            limit = headers.get("x-ratelimit-limit")
            reset = headers.get("x-ratelimit-reset")

            if remaining is not None and limit is not None and reset is not None:
                asyncio.create_task(
                    self._async_update_from_headers(
                        int(remaining), int(limit), int(reset)
                    )
                )

        except ValueError as e:
            logger.warning(
                f"Could not parse rate limit headers: {e} - Headers: {headers}"
            )
        except Exception as e:
            logger.error(f"Unexpected error updating from headers: {e}")

    async def _async_update_from_headers(
        self, remaining: int, limit: int, reset_timestamp: int
    ) -> None:
        """Async helper to update status to avoid blocking in sync context if called from one."""
        async with self._lock:
            # If the reset time from headers is different from our last known reset,
            # it might indicate a new window or more up-to-date info.
            new_reset_time = datetime.fromtimestamp(reset_timestamp, timezone.utc)
            if self._last_reset_time is None or new_reset_time > self._last_reset_time:
                self._last_reset_time = new_reset_time
                self._checked_this_reset_period = False  # New reset window, allow checking /rate_limit again if needed

            self.core_api_status = {
                "limit": limit,
                "remaining": remaining,
                "reset": reset_timestamp,
                # "used" can be calculated or might be in headers as 'x-ratelimit-used'
            }
            logger.debug(
                f"Rate limit status updated from headers. "
                f"Core: {remaining}/{limit}. Resets at: {self._last_reset_time}. Checked this period: {self._checked_this_reset_period}"
            )
