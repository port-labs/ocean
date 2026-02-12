"""
Fixed Window Rate Limiter

A standalone, async-safe fixed window rate limiter that allows up to `max_rate`
operations per `time_period` seconds. The window resets completely when the
time period expires.

This implementation is designed to be:
- Async-safe: Multiple coroutines can safely share a single instance
- Efficient: Uses asyncio primitives for coordination without busy-waiting
- Accurate: Precise window boundary calculations
- Standalone: No external dependencies beyond Python standard library and loguru

Usage examples:
    # Create a limiter with 1000 operations per minute
    limiter = FixedWindowLimiter(max_rate=1000, time_period=60.0)

    # Use as an async context manager
    async with limiter:
        # perform a rate-limited operation
        pass

    # Use the explicit acquire method
    await limiter.acquire()
    # perform a rate-limited operation

    # Decorate an async function
    @limiter.limit_function
    async def my_rate_limited_function(arg1, arg2):
        return await some_api_call(arg1, arg2)
"""

import asyncio
import time
from contextlib import AbstractAsyncContextManager
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Optional, Type

from loguru import logger


class WindowAlignmentMode(Enum):
    """
    Defines how the fixed window boundaries are aligned.

    FIRST_REQUEST: Window starts when the first request arrives.
                   Subsequent windows start when the previous one expires.

    CLOCK_ALIGNED: Window boundaries align to clock time.
                   For a 60s window, boundaries are at :00, :01, :02, etc.
                   This ensures consistent window boundaries across restarts.
    """

    FIRST_REQUEST = "first_request"
    CLOCK_ALIGNED = "clock_aligned"


class FixedWindowLimiter(AbstractAsyncContextManager[None]):
    """
    A fixed window rate limiter that allows up to `max_rate` operations per
    `time_period` seconds.

    Unlike rolling window limiters that track individual request timestamps,
    a fixed window limiter uses discrete time windows. When a window expires,
    the counter resets to zero.

    This limiter is async-safe: multiple coroutines can safely share a single
    instance. It uses asyncio.Lock and asyncio.Condition for coordination.

    Attributes:
        max_rate: Maximum number of operations allowed per window.
        time_period: Duration of each window in seconds.
        alignment: How window boundaries are calculated.
    """

    __slots__ = (
        "_max_rate",
        "_time_period",
        "_alignment",
        "_request_timeout",
        "_window_start",
        "_request_count",
        "_lock",
        "_condition",
        "_shutdown_event",
        "_metrics",
        "_logger",
    )

    def __init__(
        self,
        max_rate: int,
        time_period: float = 60.0,
        alignment: WindowAlignmentMode = WindowAlignmentMode.FIRST_REQUEST,
        request_timeout: Optional[float] = None,
    ) -> None:
        """
        Initialize a new fixed window rate limiter.

        Args:
            max_rate: Maximum number of operations allowed per window.
            time_period: Duration of the window in seconds.
            alignment: How window boundaries are aligned.
            request_timeout: Default timeout for acquire() calls (None = wait forever).

        Raises:
            ValueError: If max_rate <= 0 or time_period <= 0.
        """
        if max_rate <= 0:
            raise ValueError("max_rate must be a positive integer")
        if time_period <= 0:
            raise ValueError("time_period must be a positive number of seconds")

        self._max_rate = max_rate
        self._time_period = time_period
        self._alignment = alignment
        self._request_timeout = request_timeout

        # Window state - will be initialized on first request or based on alignment
        self._window_start: Optional[float] = None
        self._request_count: int = 0

        # Async primitives for thread safety
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)

        # Shutdown coordination
        self._shutdown_event = asyncio.Event()

        # Metrics tracking
        self._metrics: Dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "rejected_requests": 0,
            "timeouts": 0,
            "errors": 0,
            "total_wait_time": 0.0,
            "windows_reset": 0,
        }

        self._logger = logger

        self._logger.info(
            f"Created fixed window rate limiter: max_rate={max_rate}, "
            f"time_period={time_period}s, alignment={alignment.value}, "
            f"request_timeout={request_timeout}s"
        )

    @property
    def max_rate(self) -> int:
        """Maximum number of operations allowed per window."""
        return self._max_rate

    @property
    def time_period(self) -> float:
        """Duration of each window in seconds."""
        return self._time_period

    @property
    def alignment(self) -> WindowAlignmentMode:
        """How window boundaries are aligned."""
        return self._alignment

    def _get_current_time(self) -> float:
        """Get the current time. Uses monotonic clock for consistency."""
        return time.monotonic()

    def _calculate_window_start(self, current_time: float) -> float:
        """
        Calculate the start time of the current/next window based on alignment mode.

        Args:
            current_time: The current monotonic time.

        Returns:
            The start time of the window containing current_time.
        """
        if self._alignment == WindowAlignmentMode.CLOCK_ALIGNED:
            # Align to clock boundaries
            return (current_time // self._time_period) * self._time_period
        else:
            # FIRST_REQUEST mode - window starts from current time
            # This is called when resetting, so always use current time
            return current_time

    def _is_window_expired(self, current_time: float) -> bool:
        """
        Check if the current window has expired.

        Args:
            current_time: The current monotonic time.

        Returns:
            True if the window has expired, False otherwise.
        """
        if self._window_start is None:
            return True  # No window yet, treat as expired to initialize

        window_end = self._window_start + self._time_period
        return current_time >= window_end

    def _reset_window(self, current_time: float) -> None:
        """
        Reset the window to a new time period.

        Args:
            current_time: The current monotonic time.
        """
        old_window = self._window_start
        self._window_start = self._calculate_window_start(current_time)
        self._request_count = 0
        self._metrics["windows_reset"] += 1

        self._logger.debug(
            f"Window reset: old_start={old_window}, new_start={self._window_start}, "
            f"time_period={self._time_period}s"
        )

    def _time_until_reset(self, current_time: float) -> float:
        """
        Calculate the time remaining until the current window resets.

        Args:
            current_time: The current monotonic time.

        Returns:
            Time in seconds until the window resets.
        """
        if self._window_start is None:
            return 0.0

        window_end = self._window_start + self._time_period
        remaining = window_end - current_time

        # Add a tiny buffer to avoid timing edge cases
        return max(0.001, remaining)

    async def can_acquire(self) -> bool:
        """
        Check if a slot can be acquired without actually consuming it.

        This is useful for checking availability before attempting to acquire.

        Returns:
            True if a slot is available, False if rate limit is exhausted.
        """
        async with self._lock:
            current_time = self._get_current_time()

            # Check if window has expired
            if self._is_window_expired(current_time):
                return True  # New window will have capacity

            return self._request_count < self._max_rate

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a slot for an operation, waiting if necessary.

        This method waits without blocking the event loop until a slot becomes
        available or the timeout expires.

        Args:
            timeout: Maximum time to wait in seconds, or None to use the default
                    timeout set during initialization.

        Returns:
            True if a slot was acquired.

        Raises:
            asyncio.TimeoutError: If no slot could be acquired within the timeout.
            asyncio.CancelledError: If the waiting task is cancelled.
        """
        effective_timeout = timeout if timeout is not None else self._request_timeout
        start_time = self._get_current_time()
        elapsed = 0.0

        self._metrics["total_requests"] += 1

        async with self._condition:
            while not self._shutdown_event.is_set():
                current_time = self._get_current_time()
                elapsed = current_time - start_time

                # Check if we've exceeded our timeout
                if effective_timeout is not None and elapsed >= effective_timeout:
                    self._metrics["timeouts"] += 1
                    self._metrics["rejected_requests"] += 1
                    self._logger.warning(
                        f"Request timed out after {elapsed:.3f}s "
                        f"(timeout={effective_timeout}s)"
                    )
                    raise asyncio.TimeoutError(
                        f"Could not acquire rate limit slot within {effective_timeout}s"
                    )

                # Check if window has expired and reset if needed
                if self._is_window_expired(current_time):
                    self._reset_window(current_time)
                    # Notify all waiters that the window has reset
                    self._condition.notify_all()

                # Check if we can acquire a slot
                if self._request_count < self._max_rate:
                    self._request_count += 1
                    self._metrics["successful_requests"] += 1
                    self._metrics["total_wait_time"] += elapsed

                    if elapsed > 0.01:  # Only log if we actually waited
                        self._logger.debug(
                            f"Request acquired after waiting {elapsed:.3f}s, "
                            f"count={self._request_count}/{self._max_rate}"
                        )
                    else:
                        self._logger.debug(
                            f"Request acquired immediately, "
                            f"count={self._request_count}/{self._max_rate}"
                        )

                    return True

                # Calculate how long to wait
                wait_time = self._time_until_reset(current_time)

                # If we have a timeout, limit our wait time
                if effective_timeout is not None:
                    remaining_timeout = effective_timeout - elapsed
                    if remaining_timeout <= 0:
                        self._metrics["timeouts"] += 1
                        self._metrics["rejected_requests"] += 1
                        raise asyncio.TimeoutError(
                            f"Could not acquire rate limit slot within {effective_timeout}s"
                        )
                    wait_time = min(wait_time, remaining_timeout)

                self._logger.info(
                    f"Rate limit reached ({self._request_count}/{self._max_rate}), "
                    f"waiting {wait_time:.3f}s for window reset"
                )

                try:
                    # Wait for either:
                    # 1. The window to reset (we'll be notified)
                    # 2. The wait_time to elapse
                    # 3. A cancellation
                    await asyncio.wait_for(self._condition.wait(), timeout=wait_time)
                except asyncio.TimeoutError:
                    # This is expected - the wait_time elapsed
                    # Loop will continue and check the window again
                    pass
                except asyncio.CancelledError:
                    self._metrics["rejected_requests"] += 1
                    self._logger.debug(f"Request cancelled after {elapsed:.3f}s")
                    raise

        # If we get here, shutdown was triggered
        self._metrics["rejected_requests"] += 1
        raise asyncio.CancelledError("Rate limiter is shutting down")

    async def __aenter__(self) -> None:
        """
        Enter the async context manager, acquiring a slot for an operation.

        Raises:
            asyncio.TimeoutError: If no slot could be acquired within the timeout.
        """
        await self.acquire()
        return None

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        """
        Exit the async context manager. No explicit release is needed.

        Returns:
            False to not suppress exceptions.
        """
        return False

    def limit_function(
        self, func: Callable[..., Coroutine[Any, Any, Any]]
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        """
        Decorator to rate limit an asynchronous function.

        The decorated function will only be executed when the rate limit allows.

        Args:
            func: The coroutine function to rate limit.

        Returns:
            A wrapped coroutine function that respects the rate limit.

        Example:
            @limiter.limit_function
            async def my_api_call(arg1, arg2):
                return await some_external_api(arg1, arg2)
        """

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = self._get_current_time()
            try:
                async with self:
                    result = await func(*args, **kwargs)
                    return result
            finally:
                elapsed = self._get_current_time() - start_time
                self._logger.debug(
                    f"Rate-limited function {func.__name__} completed in {elapsed:.3f}s"
                )

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics for this rate limiter.

        Returns:
            Dictionary containing metrics like total requests, rejections, etc.
        """
        metrics = dict(self._metrics)

        # Calculate derived metrics
        if metrics["total_requests"] > 0:
            metrics["success_rate"] = (
                metrics["successful_requests"] / metrics["total_requests"]
            )
            metrics["rejection_rate"] = (
                metrics["rejected_requests"] / metrics["total_requests"]
            )
            if metrics["successful_requests"] > 0:
                metrics["avg_wait_time"] = (
                    metrics["total_wait_time"] / metrics["successful_requests"]
                )
            else:
                metrics["avg_wait_time"] = 0.0
        else:
            metrics["success_rate"] = 1.0
            metrics["rejection_rate"] = 0.0
            metrics["avg_wait_time"] = 0.0

        # Current window state
        metrics["current_window_usage"] = self._request_count
        metrics["current_utilization"] = (
            self._request_count / self._max_rate if self._max_rate > 0 else 0.0
        )
        metrics["max_rate"] = self._max_rate
        metrics["time_period"] = self._time_period

        return metrics

    async def shutdown(self, timeout: float = 5.0) -> None:
        """
        Gracefully shut down the rate limiter.

        This signals all waiting coroutines to stop and cleans up resources.

        Args:
            timeout: Maximum time to wait for graceful shutdown.
        """
        self._logger.info("Shutting down rate limiter")

        # Signal shutdown
        self._shutdown_event.set()

        # Wake up all waiters so they can exit
        async with self._condition:
            self._condition.notify_all()

        self._logger.info(
            f"Rate limiter shutdown completed. " f"Final metrics: {self.get_metrics()}"
        )

    async def wait_for_capacity(self) -> None:
        """
        Wait until there is capacity available in the current or next window.

        This is useful when you want to ensure capacity before starting a batch
        of operations.
        """
        async with self._condition:
            current_time = self._get_current_time()

            # If window is expired or has capacity, return immediately
            if self._is_window_expired(current_time):
                return

            if self._request_count < self._max_rate:
                return

            # Wait for window reset
            wait_time = self._time_until_reset(current_time)
            self._logger.info(f"Waiting {wait_time:.2f}s for capacity in next window")

            try:
                await asyncio.wait_for(self._condition.wait(), timeout=wait_time)
            except asyncio.TimeoutError:
                # Window should have reset, capacity available
                pass

    def reset_metrics(self) -> None:
        """Reset all metrics to their initial values."""
        self._metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "rejected_requests": 0,
            "timeouts": 0,
            "errors": 0,
            "total_wait_time": 0.0,
            "windows_reset": 0,
        }
        self._logger.info("Metrics reset")

    def __repr__(self) -> str:
        """Return a string representation of the limiter."""
        return (
            f"FixedWindowLimiter("
            f"max_rate={self._max_rate}, "
            f"time_period={self._time_period}, "
            f"alignment={self._alignment.value}, "
            f"current_count={self._request_count})"
        )
