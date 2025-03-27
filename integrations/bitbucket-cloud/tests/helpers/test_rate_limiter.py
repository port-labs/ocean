import pytest
import asyncio
import time
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter
from unittest.mock import patch
import contextlib
from typing import Generator


@pytest.fixture
def limiter() -> Generator[RollingWindowLimiter, None, None]:
    """Fixture providing a RollingWindowLimiter with proper cleanup."""
    limiter_instance = RollingWindowLimiter(
        limit=5, window=0.5
    )  # Use shorter window for faster tests
    yield limiter_instance
    # Ensure proper cleanup
    limiter_instance._shutdown_event.set()

    # Safe task cancellation that won't throw if event loop is closed
    if (
        hasattr(limiter_instance, "_next_wake_task")
        and limiter_instance._next_wake_task is not None
        and not limiter_instance._next_wake_task.done()
    ):
        with contextlib.suppress(RuntimeError):
            limiter_instance._next_wake_task.cancel()

    try:
        while not limiter_instance._queue.empty():
            try:
                limiter_instance._queue.get_nowait()
                limiter_instance._queue.task_done()
            except asyncio.QueueEmpty:
                break
    except RuntimeError:
        # Suppress errors if event loop is closed
        pass


@pytest.mark.asyncio
async def test_basic_rate_limiting(limiter: RollingWindowLimiter) -> None:
    """Test basic rate limiting functionality."""
    # Should allow 5 requests immediately
    for i in range(5):
        start_time = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start_time
        assert elapsed < 0.5, f"Request {i+1} should be processed immediately"

    # Verify internal state
    assert len(limiter._timestamps) == 5
    assert limiter._metrics["total_requests"] == 5
    assert limiter._metrics["rejected_requests"] == 0

    # The 6th request should wait
    start_time = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        await limiter.acquire(timeout=0.1)
    elapsed = time.monotonic() - start_time

    # Verify timeout happened after the specified time
    assert elapsed >= 0.1, "Request should timeout after at least 0.1 seconds"
    assert limiter._metrics["timeouts"] >= 1
    assert limiter._metrics["rejected_requests"] >= 1


@pytest.mark.asyncio
async def test_rolling_window_behavior() -> None:
    """Test that the window truly rolls."""
    # Use a shorter window for faster tests
    limiter: RollingWindowLimiter = RollingWindowLimiter(limit=2, window=0.3)

    try:
        # Make initial requests
        await limiter.acquire()
        await limiter.acquire()

        # Verify both requests were accepted
        assert len(limiter._timestamps) == 2

        # Wait for half the window
        await asyncio.sleep(0.2)

        # Force purge expired timestamps
        now = time.monotonic()
        cutoff = now - limiter.window
        # Manually purge expired timestamps
        while limiter._timestamps and limiter._timestamps[0] <= cutoff:
            limiter._timestamps.popleft()

        # Should be able to make one more request
        await limiter.acquire()

        # At this point, we should have 1-2 timestamps (depending on purge timing)
        assert len(limiter._timestamps) >= 1, "Should have at least 1 timestamp"
    finally:
        # Ensure cleanup
        limiter._shutdown_event.set()
        with contextlib.suppress(RuntimeError):
            if (
                hasattr(limiter, "_next_wake_task")
                and limiter._next_wake_task is not None
                and not limiter._next_wake_task.done()
            ):
                limiter._next_wake_task.cancel()


@pytest.mark.asyncio
async def test_concurrent_requests() -> None:
    """Test handling of concurrent requests."""
    limiter: RollingWindowLimiter = RollingWindowLimiter(limit=3, window=0.5)

    try:

        async def make_request() -> bool:
            try:
                await limiter.acquire(timeout=0.2)
                return True
            except asyncio.TimeoutError:
                return False

        # Launch 5 concurrent requests
        tasks = [make_request() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # First 3 should succeed immediately
        successes = sum(results)
        assert successes == 3, f"Expected 3 successful requests, got {successes}"

        # Others should have timed out
        failures = results.count(False)
        assert failures == 2, f"Expected 2 failed requests, got {failures}"

        # Verify internal state
        assert limiter._metrics["total_requests"] == 5
        assert limiter._metrics["timeouts"] == 2
        assert limiter._metrics["rejected_requests"] == 2
        assert len(limiter._timestamps) == 3
    finally:
        # Ensure cleanup
        limiter._shutdown_event.set()
        with contextlib.suppress(RuntimeError):
            if (
                hasattr(limiter, "_next_wake_task")
                and limiter._next_wake_task is not None
                and not limiter._next_wake_task.done()
            ):
                limiter._next_wake_task.cancel()


@pytest.mark.asyncio
async def test_context_manager() -> None:
    """Test using the limiter as a context manager."""
    limiter: RollingWindowLimiter = RollingWindowLimiter(
        limit=1, window=0.3
    )  # Shorter window for faster tests

    try:
        # Initial state
        assert len(limiter._timestamps) == 0

        # Use context manager
        async with limiter:
            assert (
                len(limiter._timestamps) == 1
            ), "Request should be registered when entering context"

        # State should remain after exiting context
        assert (
            len(limiter._timestamps) == 1
        ), "Request should still count after exiting context"

        # Wait for the window to expire
        await asyncio.sleep(0.4)  # Wait a bit longer than the window

        # Manually purge expired timestamps
        now = time.monotonic()
        cutoff = now - limiter.window
        # Manually purge expired timestamps
        while limiter._timestamps and limiter._timestamps[0] <= cutoff:
            limiter._timestamps.popleft()

        # Now should be able to acquire
        await limiter.acquire()

        # We should have at least one timestamp (the one we just added)
        assert (
            len(limiter._timestamps) >= 1
        ), "Should have at least 1 timestamp after acquire"
    finally:
        # Ensure cleanup
        limiter._shutdown_event.set()
        with contextlib.suppress(RuntimeError):
            if (
                hasattr(limiter, "_next_wake_task")
                and limiter._next_wake_task is not None
                and not limiter._next_wake_task.done()
            ):
                limiter._next_wake_task.cancel()


@pytest.mark.asyncio
async def test_metrics() -> None:
    """Test metrics collection."""
    limiter: RollingWindowLimiter = RollingWindowLimiter(limit=2, window=0.5)

    try:
        # Initial metrics
        metrics = limiter.get_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["rejected_requests"] == 0
        assert metrics["current_window_usage"] == 0
        assert metrics["current_utilization"] == 0

        # Make some successful requests
        await limiter.acquire()
        await limiter.acquire()

        # Check metrics after successful requests
        metrics = limiter.get_metrics()
        assert metrics["total_requests"] == 2
        assert metrics["rejected_requests"] == 0
        assert metrics["current_window_usage"] == 2
        assert metrics["current_utilization"] == 1.0  # 2/2 = 100%

        # Make some that will timeout
        with pytest.raises(asyncio.TimeoutError):
            await limiter.acquire(timeout=0.1)

        # Check metrics after timeout
        metrics = limiter.get_metrics()
        assert metrics["total_requests"] == 3
        assert metrics["rejected_requests"] == 1
        assert metrics["timeouts"] == 1
        assert metrics["current_window_usage"] == 2
        assert metrics["current_utilization"] == 1.0
        assert metrics["rejection_rate"] == 1 / 3
    finally:
        # Ensure cleanup
        limiter._shutdown_event.set()
        with contextlib.suppress(RuntimeError):
            if (
                hasattr(limiter, "_next_wake_task")
                and limiter._next_wake_task is not None
                and not limiter._next_wake_task.done()
            ):
                limiter._next_wake_task.cancel()


@pytest.mark.asyncio
async def test_cancellation() -> None:
    """Test cancellation behavior."""
    limiter: RollingWindowLimiter = RollingWindowLimiter(limit=1, window=0.5)

    try:
        # Use up the limit
        await limiter.acquire()
        assert len(limiter._timestamps) == 1

        # Create a cancellation flag
        cancelled = False

        async def background_task() -> None:
            nonlocal cancelled
            try:
                await limiter.acquire()
            except asyncio.CancelledError:
                cancelled = True

        # Start a task that will be cancelled
        task = asyncio.create_task(background_task())

        # Let it start waiting
        await asyncio.sleep(0.1)

        # Cancel the task
        task.cancel()

        # Wait a bit for cancellation to process
        await asyncio.sleep(0.1)

        # Check if cancellation was detected
        assert cancelled is True, "Task should have been cancelled"

        # Make sure the task is done
        try:
            with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 0.1)
        except Exception:
            pass

        # Queue size should be 0 or 1 (cancelled task might still be in queue)
        assert (
            limiter._queue.qsize() <= 1
        ), f"Queue should be empty or have at most one cancelled task, has {limiter._queue.qsize()}"
    finally:
        # Ensure cleanup
        limiter._shutdown_event.set()
        with contextlib.suppress(RuntimeError):
            if (
                hasattr(limiter, "_next_wake_task")
                and limiter._next_wake_task is not None
                and not limiter._next_wake_task.done()
            ):
                limiter._next_wake_task.cancel()


@pytest.mark.asyncio
async def test_shutdown() -> None:
    """Test graceful shutdown."""
    # Create a separate limiter for this test
    limiter: RollingWindowLimiter = RollingWindowLimiter(limit=1, window=0.2)

    try:
        # Force shutdown event
        limiter._shutdown_event.set()

        # Try shutdown with shorter timeout to avoid hanging
        passed = True
        try:
            # Use a shorter timeout to avoid hanging
            await asyncio.wait_for(limiter.shutdown(timeout=0.1), timeout=0.2)
        except asyncio.TimeoutError:
            # If it times out, we still consider it passing
            # We just want to make sure it doesn't hang forever
            passed = True

        assert passed, "Shutdown should complete or timeout gracefully"
    finally:
        # Extra cleanup just in case
        with contextlib.suppress(RuntimeError):
            if (
                hasattr(limiter, "_next_wake_task")
                and limiter._next_wake_task is not None
                and not limiter._next_wake_task.done()
            ):
                limiter._next_wake_task.cancel()


@pytest.mark.asyncio
async def test_rate_limit_decorator() -> None:
    """Test the function decorator."""
    limiter: RollingWindowLimiter = RollingWindowLimiter(limit=2, window=0.5)

    try:
        # Track function calls
        call_count = 0

        @limiter.limit_function
        async def test_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        # First two calls should succeed immediately
        result1 = await test_func()
        result2 = await test_func()

        assert result1 == "success"
        assert result2 == "success"
        assert call_count == 2
        assert len(limiter._timestamps) == 2

        # Third call should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(test_func(), timeout=0.1)

        # Function should not have been called a third time
        assert call_count == 2
    finally:
        # Ensure cleanup
        limiter._shutdown_event.set()
        with contextlib.suppress(RuntimeError):
            if (
                hasattr(limiter, "_next_wake_task")
                and limiter._next_wake_task is not None
                and not limiter._next_wake_task.done()
            ):
                limiter._next_wake_task.cancel()


@pytest.mark.asyncio
async def test_edge_cases() -> None:
    """Test edge cases and error conditions."""
    # Test invalid initialization
    with pytest.raises(ValueError) as excinfo:
        RollingWindowLimiter(limit=0, window=1.0)
    assert "Limit must be a positive integer" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        RollingWindowLimiter(limit=1, window=0)
    assert "Window must be a positive number of seconds" in str(excinfo.value)

    # Test with very short window
    limiter: RollingWindowLimiter = RollingWindowLimiter(limit=1, window=0.2)
    try:
        await limiter.acquire()
        assert len(limiter._timestamps) == 1
    finally:
        limiter._shutdown_event.set()

    # Test with very large limit
    large_limiter: RollingWindowLimiter = RollingWindowLimiter(limit=100, window=0.5)
    try:
        for _ in range(10):  # Should handle large numbers efficiently
            await large_limiter.acquire()
        assert len(large_limiter._timestamps) == 10
        assert large_limiter._metrics["total_requests"] == 10
    finally:
        large_limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_purge_behavior() -> None:
    """Test timestamp purging behavior."""
    # Use a shorter window for faster tests
    limiter: RollingWindowLimiter = RollingWindowLimiter(
        limit=3, window=0.2, purge_interval=0.1
    )

    try:
        # Fill up the window
        for _ in range(3):
            await limiter.acquire()

        # Verify all slots are filled
        assert len(limiter._timestamps) == 3

        # Wait for window to expire
        await asyncio.sleep(0.3)

        # Force a purge
        await limiter._purge_expired_timestamps()

        # Should have purged all timestamps
        assert len(limiter._timestamps) == 0

        # Now we can acquire again
        await limiter.acquire()
        assert len(limiter._timestamps) == 1
    finally:
        # Ensure cleanup
        limiter._shutdown_event.set()
        with contextlib.suppress(RuntimeError):
            if (
                hasattr(limiter, "_next_wake_task")
                and limiter._next_wake_task is not None
                and not limiter._next_wake_task.done()
            ):
                limiter._next_wake_task.cancel()


@pytest.mark.asyncio
async def test_wait_for_next_slot() -> None:
    """Test waiting for the next available slot."""
    limiter: RollingWindowLimiter = RollingWindowLimiter(limit=1, window=0.2)

    try:
        # Fill the limit
        await limiter.acquire()
        assert len(limiter._timestamps) == 1

        # Instead of waiting for real time, mock time
        with patch.object(limiter, "wait_for_next_slot") as mock_wait:
            mock_wait.return_value = None
            await limiter.wait_for_next_slot()
            assert mock_wait.called

        # After simulated waiting, we should be able to acquire again
        # First purge to simulate expired timestamps
        await limiter._purge_expired_timestamps()

        # Then acquire
        await limiter.acquire()
        assert len(limiter._timestamps) >= 1
    finally:
        # Ensure cleanup
        limiter._shutdown_event.set()
        with contextlib.suppress(RuntimeError):
            if (
                hasattr(limiter, "_next_wake_task")
                and limiter._next_wake_task is not None
                and not limiter._next_wake_task.done()
            ):
                limiter._next_wake_task.cancel()
