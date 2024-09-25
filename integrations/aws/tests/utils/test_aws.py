import unittest
from unittest.mock import AsyncMock, patch
from typing import AsyncGenerator, Any
from utils.aws import update_available_access_credentials
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


class TestUpdateAvailableAccessCredentials(unittest.IsolatedAsyncioTestCase):
    """Test cases to simulate and handle the thundering herd problem in AWS credentials reset."""

    @staticmethod
    async def _run_update_access_iterator_result() -> AsyncGenerator[bool, None]:
        result = await update_available_access_credentials()
        yield result

    @staticmethod
    async def _create_iterator_tasks(func: Any, count: int) -> Any:
        """Helper to create async tasks."""
        return [func() for _ in range(count)]

    @patch("utils.aws._session_manager.reset", new_callable=AsyncMock)
    @patch("utils.aws.lock", new_callable=AsyncMock)
    async def test_multiple_task_execution(
        self, mock_lock: Any, mock_reset: Any
    ) -> None:
        tasks = await self._create_iterator_tasks(
            self._run_update_access_iterator_result, 10
        )
        async for result in stream_async_iterators_tasks(*tasks):
            self.assertTrue(result)

        # Assert that the reset method was awaited exactly once (i.e., no thundering herd)
        mock_reset.assert_awaited_once()

        mock_lock.__aenter__.assert_awaited_once()
        mock_lock.__aexit__.assert_awaited_once()
