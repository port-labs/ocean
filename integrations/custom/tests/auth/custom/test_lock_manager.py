"""Tests for LockManager class"""

import asyncio
import pytest

from http_server.auth.custom.lock_manager import LockManager


@pytest.mark.asyncio
class TestLockManager:
    """Test LockManager"""

    def test_init_creates_lock(self) -> None:
        """Test that LockManager initializes with an asyncio.Lock"""
        manager = LockManager()

        assert manager.lock is not None
        assert isinstance(manager.lock, asyncio.Lock)

    async def test_lock_prevents_concurrent_access(self) -> None:
        """Test that the lock can be used to prevent concurrent access"""
        manager = LockManager()
        access_count = []

        async def critical_section() -> None:
            async with manager.lock:
                access_count.append(1)
                await asyncio.sleep(0.01)  # Simulate some work
                access_count.append(2)

        # Run two coroutines concurrently
        await asyncio.gather(critical_section(), critical_section())

        # With lock, access should be serialized: [1, 2, 1, 2]
        # Without lock, it could be: [1, 1, 2, 2]
        assert len(access_count) == 4
        # Verify serialization - first critical section completes before second starts
        assert access_count[0] == 1
        assert access_count[1] == 2
        assert access_count[2] == 1
        assert access_count[3] == 2
