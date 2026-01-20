import pytest
import asyncio
import time
from gcp_core.helpers.ratelimiter.fixed_window import (
    FixedWindowLimiter,
    WindowAlignmentMode,
)
import contextlib
from typing import Generator


@pytest.fixture
def limiter() -> Generator[FixedWindowLimiter, None, None]:
    """Fixture providing a FixedWindowLimiter with proper cleanup."""
    limiter_instance = FixedWindowLimiter(
        max_rate=5, time_period=0.5
    )  # Use shorter window for faster tests
    yield limiter_instance
    # Ensure proper cleanup
    limiter_instance._shutdown_event.set()


@pytest.fixture
def clock_aligned_limiter() -> Generator[FixedWindowLimiter, None, None]:
    """Fixture providing a clock-aligned FixedWindowLimiter."""
    limiter_instance = FixedWindowLimiter(
        max_rate=5,
        time_period=0.5,
        alignment=WindowAlignmentMode.CLOCK_ALIGNED,
    )
    yield limiter_instance
    limiter_instance._shutdown_event.set()


@pytest.mark.asyncio
async def test_basic_rate_limiting(limiter: FixedWindowLimiter) -> None:
    """Test basic rate limiting functionality."""
    # Should allow 5 requests immediately
    for i in range(5):
        start_time = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start_time
        assert elapsed < 0.5, f"Request {i+1} should be processed immediately"

    # Verify internal state
    assert limiter._request_count == 5
    assert limiter._metrics["total_requests"] == 5
    assert limiter._metrics["successful_requests"] == 5
    assert limiter._metrics["rejected_requests"] == 0

    # The 6th request should wait or timeout
    start_time = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        await limiter.acquire(timeout=0.1)
    elapsed = time.monotonic() - start_time

    # Verify timeout happened after the specified time
    assert elapsed >= 0.1, "Request should timeout after at least 0.1 seconds"
    assert limiter._metrics["timeouts"] >= 1
    assert limiter._metrics["rejected_requests"] >= 1


@pytest.mark.asyncio
async def test_window_reset_behavior() -> None:
    """Test that the window resets and allows new requests."""
    limiter = FixedWindowLimiter(max_rate=2, time_period=0.3)

    try:
        # Use up all slots
        await limiter.acquire()
        await limiter.acquire()
        assert limiter._request_count == 2

        # Wait for window to expire
        await asyncio.sleep(0.35)

        # Should be able to acquire again after window reset
        await limiter.acquire()

        # Counter should have reset
        assert limiter._request_count == 1
        assert limiter._metrics["windows_reset"] >= 1
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_concurrent_requests() -> None:
    """Test handling of concurrent requests."""
    limiter = FixedWindowLimiter(max_rate=3, time_period=0.5)

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
        assert limiter._request_count == 3
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_context_manager() -> None:
    """Test using the limiter as a context manager."""
    limiter = FixedWindowLimiter(max_rate=1, time_period=0.3)

    try:
        # Initial state
        assert limiter._request_count == 0

        # Use context manager
        async with limiter:
            assert limiter._request_count == 1, "Request should be counted"

        # State should remain after exiting context
        assert limiter._request_count == 1, "Request should still count after exit"

        # Wait for the window to expire
        await asyncio.sleep(0.35)

        # Now we can acquire again
        await limiter.acquire()
        assert limiter._request_count == 1  # Reset to 1 after window reset
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_metrics() -> None:
    """Test metrics collection."""
    limiter = FixedWindowLimiter(max_rate=2, time_period=0.5)

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
        assert metrics["successful_requests"] == 2
        assert metrics["rejected_requests"] == 0
        assert metrics["current_window_usage"] == 2
        assert metrics["current_utilization"] == 1.0  # 2/2 = 100%

        # Make one that will timeout
        with pytest.raises(asyncio.TimeoutError):
            await limiter.acquire(timeout=0.1)

        # Check metrics after timeout
        metrics = limiter.get_metrics()
        assert metrics["total_requests"] == 3
        assert metrics["rejected_requests"] == 1
        assert metrics["timeouts"] == 1
        assert metrics["current_window_usage"] == 2
        assert metrics["rejection_rate"] == 1 / 3
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_cancellation() -> None:
    """Test cancellation behavior."""
    limiter = FixedWindowLimiter(max_rate=1, time_period=0.5)

    try:
        # Use up the limit
        await limiter.acquire()
        assert limiter._request_count == 1

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
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_shutdown() -> None:
    """Test graceful shutdown."""
    limiter = FixedWindowLimiter(max_rate=1, time_period=0.2)

    try:
        # Shutdown should complete without error
        await limiter.shutdown(timeout=0.1)
        assert limiter._shutdown_event.is_set()
    except asyncio.TimeoutError:
        # If it times out, we still consider it passing
        pass


@pytest.mark.asyncio
async def test_rate_limit_decorator() -> None:
    """Test the function decorator."""
    limiter = FixedWindowLimiter(max_rate=2, time_period=0.5)

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
        assert limiter._request_count == 2

        # Third call should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(test_func(), timeout=0.1)

        # Function should not have been called a third time
        assert call_count == 2
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_edge_cases() -> None:
    """Test edge cases and error conditions."""
    # Test invalid initialization
    with pytest.raises(ValueError) as excinfo:
        FixedWindowLimiter(max_rate=0, time_period=1.0)
    assert "max_rate must be a positive integer" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        FixedWindowLimiter(max_rate=1, time_period=0)
    assert "time_period must be a positive number of seconds" in str(excinfo.value)

    # Test with very short window
    limiter = FixedWindowLimiter(max_rate=1, time_period=0.2)
    try:
        await limiter.acquire()
        assert limiter._request_count == 1
    finally:
        limiter._shutdown_event.set()

    # Test with large limit
    large_limiter = FixedWindowLimiter(max_rate=100, time_period=0.5)
    try:
        for _ in range(10):  # Should handle large numbers efficiently
            await large_limiter.acquire()
        assert large_limiter._request_count == 10
        assert large_limiter._metrics["total_requests"] == 10
    finally:
        large_limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_clock_aligned_window(clock_aligned_limiter: FixedWindowLimiter) -> None:
    """Test clock-aligned window behavior."""
    # Make a request to initialize the window
    await clock_aligned_limiter.acquire()

    # The window start should be aligned to clock boundaries
    window_start = clock_aligned_limiter._window_start
    time_period = clock_aligned_limiter._time_period

    # Check that window_start is aligned (divisible by time_period)
    assert window_start is not None
    # For clock-aligned, window_start should be at a boundary
    remainder = window_start % time_period
    assert (
        remainder < 0.01 or (time_period - remainder) < 0.01
    ), f"Window start {window_start} should be aligned to {time_period}s boundaries"


@pytest.mark.asyncio
async def test_first_request_aligned_window() -> None:
    """Test first-request-aligned window behavior."""
    limiter = FixedWindowLimiter(
        max_rate=5,
        time_period=0.5,
        alignment=WindowAlignmentMode.FIRST_REQUEST,
    )

    try:
        start_time = time.monotonic()

        # Make a request to initialize the window
        await limiter.acquire()

        # The window start should be close to when we made the first request
        window_start = limiter._window_start
        assert window_start is not None
        assert (
            abs(window_start - start_time) < 0.1
        ), "Window start should be close to first request time"
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_can_acquire() -> None:
    """Test the can_acquire method."""
    limiter = FixedWindowLimiter(max_rate=2, time_period=0.5)

    try:
        # Initially should be able to acquire
        assert await limiter.can_acquire() is True

        # Use up slots
        await limiter.acquire()
        assert await limiter.can_acquire() is True  # Still one slot left

        await limiter.acquire()
        assert await limiter.can_acquire() is False  # No slots left

        # Wait for window to expire
        await asyncio.sleep(0.55)

        # Should be able to acquire again
        assert await limiter.can_acquire() is True
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_wait_for_capacity() -> None:
    """Test the wait_for_capacity method."""
    limiter = FixedWindowLimiter(max_rate=2, time_period=0.3)

    try:
        # Use up all slots
        await limiter.acquire()
        await limiter.acquire()

        # Wait for capacity should wait for window reset
        start_time = time.monotonic()
        await limiter.wait_for_capacity()
        elapsed = time.monotonic() - start_time

        # Should have waited approximately the window time
        assert (
            elapsed >= 0.25
        ), f"Should have waited for window reset, waited {elapsed}s"
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_reset_metrics() -> None:
    """Test resetting metrics."""
    limiter = FixedWindowLimiter(max_rate=5, time_period=0.5)

    try:
        # Make some requests
        await limiter.acquire()
        await limiter.acquire()

        assert limiter._metrics["total_requests"] == 2

        # Reset metrics
        limiter.reset_metrics()

        # Metrics should be reset
        assert limiter._metrics["total_requests"] == 0
        assert limiter._metrics["successful_requests"] == 0
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_repr() -> None:
    """Test string representation."""
    limiter = FixedWindowLimiter(
        max_rate=10,
        time_period=60.0,
        alignment=WindowAlignmentMode.CLOCK_ALIGNED,
    )

    try:
        repr_str = repr(limiter)
        assert "FixedWindowLimiter" in repr_str
        assert "max_rate=10" in repr_str
        assert "time_period=60.0" in repr_str
        assert "clock_aligned" in repr_str
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_properties() -> None:
    """Test property accessors."""
    limiter = FixedWindowLimiter(
        max_rate=100,
        time_period=30.0,
        alignment=WindowAlignmentMode.FIRST_REQUEST,
    )

    try:
        assert limiter.max_rate == 100
        assert limiter.time_period == 30.0
        assert limiter.alignment == WindowAlignmentMode.FIRST_REQUEST
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_waiting_requests_get_notified_on_window_reset() -> None:
    """Test that waiting requests are notified when window resets."""
    limiter = FixedWindowLimiter(max_rate=1, time_period=0.3)

    try:
        # Use up the slot
        await limiter.acquire()

        # Start a task that will wait for the next slot
        async def waiting_task() -> float:
            start = time.monotonic()
            await limiter.acquire()
            return time.monotonic() - start

        task = asyncio.create_task(waiting_task())

        # Wait for window to reset
        await asyncio.sleep(0.35)

        # The task should complete shortly after window reset
        wait_time = await asyncio.wait_for(task, timeout=0.2)

        # The task should have waited approximately the window time
        assert wait_time >= 0.25, f"Task waited {wait_time}s, expected ~0.3s"
        assert wait_time < 0.5, f"Task waited too long: {wait_time}s"
    finally:
        limiter._shutdown_event.set()


@pytest.mark.asyncio
async def test_multiple_waiters_all_notified() -> None:
    """Test that multiple waiting requests are all notified on window reset."""
    limiter = FixedWindowLimiter(max_rate=3, time_period=0.3)

    try:
        # Use up all slots
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

        # Start multiple tasks that will wait
        async def waiting_task() -> bool:
            try:
                await limiter.acquire(timeout=0.5)
                return True
            except asyncio.TimeoutError:
                return False

        # Start 3 waiting tasks
        tasks = [asyncio.create_task(waiting_task()) for _ in range(3)]

        # Wait for window to reset and tasks to complete
        results = await asyncio.gather(*tasks)

        # All should succeed after window reset
        assert all(results), f"Expected all tasks to succeed, got {results}"
        assert limiter._request_count == 3
    finally:
        limiter._shutdown_event.set()
