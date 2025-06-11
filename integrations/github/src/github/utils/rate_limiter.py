import asyncio
import time
from collections import deque
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import (
    Optional,
    Dict,
    Any,
    Callable,
    Coroutine,
    Deque,
    Tuple,
    Type,
)

from loguru import logger


@dataclass
class GitHubRateLimiter:
    """Config for BitBucket v2 API rate limiter"""

    WINDOW_TTL: int = 3600  # rate limit timespan in seconds
    LIMIT: int = 1000  # request limit allowed per second


class RollingWindowLimiter(AbstractAsyncContextManager[None]):
    """
    A rolling window rate limiter that allows up to `limit` operations per `window` seconds.

    This implementation uses a deque to track the timestamps of recent operations and
    asyncio.Queue for managing pending requests. It efficiently schedules the processing
    of requests as soon as capacity becomes available in the rolling window.

    Features:
    - Precise rolling window implementation
    - Thread-safe and race-condition-resistant using asyncio primitives
    - Efficient scheduling with exact wake-up timing
    - Built-in metrics and logging for monitoring
    - Configurable timeouts to prevent deadlocks

    Usage examples:
        # Create a limiter with 1000 operations per hour
        limiter = RollingWindowLimiter(limit=1000, window=3600)

        # Use as an async context manager
        async with limiter:
            # perform a rate-limited operation

        # Use the explicit acquire method
        await limiter.acquire()
        try:
            # perform a rate-limited operation
        finally:
            # No release needed - the operation is automatically counted
            pass

        # Decorate an async function
        @limiter.limit_function
        async def my_rate_limited_function(arg1, arg2):
            # This function is now a rate-limited
            return await some_api_call(arg1, arg2)
    """

    __slots__ = (
        "limit",
        "window",
        "_timestamps",
        "_lock",
        "_condition",
        "_queue",
        "_processing",
        "_next_wake_task",
        "_logger",
        "_metrics",
        "_timestamp_last_purged",
        "_purge_interval",
        "_request_timeout",
        "_task_timeout",
        "_shutdown_event",
    )

    def __init__(
        self,
        limit: int,
        window: float,
        purge_interval: float = 1.0,
        request_timeout: Optional[float] = None,
        task_timeout: Optional[float] = None,
    ):
        """
        Initialize a new rolling window rate limiter.

        Args:
            limit: Maximum number of operations allowed per rolling window.
            window: Duration of the window in seconds.
            purge_interval: How often to purge expired timestamps (in seconds).
            request_timeout: Timeout for waiting on rate limit (None = wait forever).
            task_timeout: Timeout for processing queued tasks (None = no timeout).

        Raises:
            ValueError: If limit <= 0 or window <= 0.
        """
        if limit <= 0:
            raise ValueError("Limit must be a positive integer")
        if window <= 0:
            raise ValueError("Window must be a positive number of seconds")

        self.limit = limit
        self.window = window
        self._timestamps: Deque[float] = deque()
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
        self._queue: asyncio.Queue[Tuple[asyncio.Future[None], float]] = asyncio.Queue()
        self._processing = False
        self._next_wake_task: Optional[asyncio.Task[None]] = None
        self._timestamp_last_purged = time.monotonic()
        self._purge_interval = purge_interval
        self._request_timeout = request_timeout
        self._task_timeout = task_timeout
        self._shutdown_event = asyncio.Event()

        self._logger = logger
        self._metrics = {
            "total_requests": 0,
            "rejected_requests": 0,
            "timeouts": 0,
            "errors": 0,
            "current_queue_size": 0,
            "max_queue_size": 0,
            "total_wait_time": 0.0,
        }

        self._logger.info(
            f"Created rate limiter: limit={limit}, window={window}s, "
            f"purge_interval={purge_interval}s, request_timeout={request_timeout}s"
        )

    async def _safe_cancel_task(self, task: Optional[asyncio.Task[None]]) -> None:
        """
        Safely cancel a task handling potential exceptions.

        Args:
            task: The task to cancel, or None.
        """
        if task and not task.done():
            try:
                task.cancel()
                # Wait for the task to be canceled, with a short timeout
                try:
                    await asyncio.wait_for(task, timeout=0.1)
                except asyncio.TimeoutError:
                    self._logger.warning("Task cancellation timed out")
                except asyncio.CancelledError:
                    pass  # This is expected
            except Exception as e:
                self._logger.warning(f"Error cancelling task: {e}")

    async def _purge_expired_timestamps(self) -> None:
        """
        Remove timestamps that have fallen outside the rolling window.
        This is critical for the rolling window behavior - we must accurately
        track which operations have expired from the window.
        """
        now = time.monotonic()
        cutoff = now - self.window

        purged_count = 0

        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()
            purged_count += 1

        if purged_count > 0:
            self._logger.debug(f"Purged {purged_count} expired timestamps")
            self._timestamp_last_purged = now

    async def _process_next_request(self) -> bool:
        """
        Process a single request from the queue if capacity is available.

        Returns:
            bool: True if a request was processed, False otherwise.
        """
        now = time.monotonic()

        if len(self._timestamps) < self.limit and not self._queue.empty():
            future, enqueue_time = await self._queue.get()

            wait_time = time.monotonic() - enqueue_time
            self._metrics["total_wait_time"] += wait_time
            self._metrics["current_queue_size"] = self._queue.qsize()

            self._timestamps.append(now)

            if not future.done():
                future.set_result(None)
                self._logger.debug(
                    f"Request processed after waiting {wait_time:.6f}s, "
                    f"queue_size={self._queue.qsize()}"
                )
            else:
                self._logger.warning("Future was already done (canceled or timed out)")

            self._queue.task_done()
            return True

        return False

    async def _calculate_next_slot_time(self) -> float:
        """
        Calculate the time until the next slot becomes available.

        This method is critical for the rolling window behavior - it must return
        the exact time until the oldest operation expires from the window.

        Returns:
            float: Time in seconds until the next slot will be available.
        """
        now = time.monotonic()

        if not self._timestamps:
            return 0.0

        earliest = self._timestamps[0]
        next_available = earliest + self.window

        wait_time = next_available - now

        # Added a tiny minimum to prevent CPU spinning but keeping it very small
        # to maintain the true rolling window behavior
        return max(0.001, wait_time)

    async def _process_queue(self) -> None:
        """
        Process pending operations from the queue as capacity becomes available.
        Handles errors gracefully and ensures the processing state is always reset.
        """
        if self._processing:
            return

        self._processing = True
        self._logger.debug("Starting queue processing")

        try:
            while not self._queue.empty() and not self._shutdown_event.is_set():
                await self._purge_expired_timestamps()

                processed = await self._process_next_request()

                if not processed and not self._queue.empty():
                    # Calculate the *exact* time when the next slot opens up
                    # This is crucial for a true rolling window - we must wake up precisely
                    # when the oldest request expires from our window
                    wait_time = await self._calculate_next_slot_time()

                    self._logger.info(
                        f"Will process next request in {wait_time:.6f}s when oldest timestamp expires"
                    )

                    try:
                        await self._safe_cancel_task(self._next_wake_task)

                        self._next_wake_task = asyncio.create_task(
                            asyncio.sleep(wait_time)
                        )

                        await self._next_wake_task
                    except asyncio.CancelledError:
                        self._logger.debug("Wake-up task was canceled")
                    finally:
                        self._next_wake_task = None
        except Exception as e:
            self._logger.error(f"Error during queue processing: {e}", exc_info=True)
            self._metrics["errors"] += 1
        finally:
            self._processing = False

            if not self._queue.empty() and not self._shutdown_event.is_set():
                self._logger.debug("Restarting queue processing")
                asyncio.create_task(self._process_queue())
            else:
                self._logger.debug("Queue processing completed")

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a slot for an operation, waiting if necessary.

        This method waits without blocking the event loop until a slot becomes
        available or the timeout expires.

        Args:
            timeout: Maximum time to wait in seconds, or None to use the default
                    timeout set during initialization.

        Returns:
            bool: True if a slot was acquired, False if timed out.

        Raises:
            asyncio.TimeoutError: If no slot could be acquired within the timeout.
            Asyncio.CancelledError: If the waiting task is canceled.
        """
        effective_timeout = timeout if timeout is not None else self._request_timeout

        self._metrics["total_requests"] += 1
        start_time = time.monotonic()

        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window
            purged_count = 0
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()
                purged_count += 1

            if purged_count > 0:
                self._logger.debug(
                    f"Purged {purged_count} expired timestamps during acquire"
                )

            if len(self._timestamps) < self.limit:
                self._timestamps.append(now)
                self._logger.debug("Request processed immediately")
                return True

            future: asyncio.Future[None] = asyncio.Future()

            await self._queue.put((future, start_time))

            queue_size = self._queue.qsize()
            self._metrics["current_queue_size"] = queue_size
            self._metrics["max_queue_size"] = max(
                self._metrics["max_queue_size"], queue_size
            )

            self._logger.debug(f"Request enqueued, queue_size={queue_size}")

        # Start queue processing if not already running
        if not self._processing:
            asyncio.create_task(self._process_queue())

        try:
            if effective_timeout is not None:
                await asyncio.wait_for(future, timeout=effective_timeout)
            else:
                await future
            return True
        except asyncio.TimeoutError:
            self._metrics["timeouts"] += 1
            self._metrics["rejected_requests"] += 1
            self._logger.warning(
                f"Request timed out after {time.monotonic() - start_time:.6f}s"
            )
            raise
        except asyncio.CancelledError:
            self._metrics["rejected_requests"] += 1
            self._logger.debug(
                f"Request cancelled after {time.monotonic() - start_time:.6f}s"
            )
            raise
        except Exception as e:
            self._metrics["errors"] += 1
            self._logger.error(
                f"Error while waiting for rate limit: {e}", exc_info=True
            )
            raise

    async def __aenter__(self) -> None:
        """
        Enter the async context manager, acquiring a slot for an operation.

        Returns:
            None

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
        Decorator that applies rate limiting to an async function.

        Args:
            func: The async function to rate limit.

        Returns:
            A wrapped version of the function that respects rate limits.
        """
        import inspect
        is_async_generator = inspect.isasyncgenfunction(func)

        if is_async_generator:
            async def generator_wrapper(*args: Any, **kwargs: Any) -> Any:
                async with self:
                    async for item in func(*args, **kwargs):
                        yield item
            return generator_wrapper
        else:
            async def function_wrapper(*args: Any, **kwargs: Any) -> Any:
                async with self:
                    return await func(*args, **kwargs)
            return function_wrapper

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics for this rate limiter.

        Returns:
            Dictionary containing metrics like total requests, rejections, etc.
        """
        metrics = dict(self._metrics)

        if metrics["total_requests"] > 0:
            metrics["rejection_rate"] = (
                metrics["rejected_requests"] / metrics["total_requests"]
            )
            if metrics["total_requests"] - metrics["rejected_requests"] > 0:
                metrics["avg_wait_time"] = metrics["total_wait_time"] / (
                    metrics["total_requests"] - metrics["rejected_requests"]
                )
            else:
                metrics["avg_wait_time"] = 0
        else:
            metrics["rejection_rate"] = 0
            metrics["avg_wait_time"] = 0

        metrics["current_window_usage"] = len(self._timestamps)
        metrics["current_utilization"] = (
            len(self._timestamps) / self.limit if self.limit > 0 else 0
        )

        return metrics

    async def shutdown(self, timeout: float = 5.0) -> None:
        """
        Gracefully shut down the rate limiter.

        This cancels any pending requests and cleans up resources.

        Args:
            timeout: Maximum time to wait for graceful shutdown.

        Raises:
            asyncio.TimeoutError: If shutdown doesn't complete within timeout.
        """
        self._logger.info("Shutting down rate limiter")

        self._shutdown_event.set()

        await self._safe_cancel_task(self._next_wake_task)

        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
            self._logger.info("Rate limiter shutdown completed")
        except asyncio.TimeoutError:
            self._logger.warning(
                f"Rate limiter shutdown timed out after {timeout}s "
                f"with {self._queue.qsize()} pending requests"
            )
            raise

    async def wait_for_next_slot(self) -> None:
        """Wait until the next slot becomes available in the rolling window."""
        now = time.monotonic()
        if not self._timestamps:
            return None

        earliest = self._timestamps[0]
        next_available = earliest + self.window
        wait_time = max(0.001, next_available - now)

        self._logger.info(f"Waiting {wait_time:.2f} seconds for next available slot")
        await asyncio.sleep(wait_time)
        self._timestamps.popleft()
        return None
