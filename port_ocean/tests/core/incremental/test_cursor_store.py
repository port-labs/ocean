"""Unit tests for CursorStore."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.core.incremental.cursor_store import CursorStore


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.get_integration_cursor = AsyncMock(return_value=None)
    client.upsert_integration_cursor = AsyncMock()
    return client


@pytest.fixture
def cursor_store(mock_port_client: MagicMock) -> CursorStore:
    return CursorStore(mock_port_client)


@pytest.fixture
def cursor() -> datetime:
    return datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestCursorStoreGet:
    async def test_returns_none_when_no_cursor_stored(
        self, cursor_store: CursorStore, mock_port_client: MagicMock
    ) -> None:
        mock_port_client.get_integration_cursor.return_value = None
        result = await cursor_store.get("issue", 0)
        assert result is None
        mock_port_client.get_integration_cursor.assert_called_once_with("issue", 0)

    async def test_returns_cursor_when_stored(
        self,
        cursor_store: CursorStore,
        mock_port_client: MagicMock,
        cursor: datetime,
    ) -> None:
        mock_port_client.get_integration_cursor.return_value = cursor
        result = await cursor_store.get("pull-request", 1)
        assert result == cursor
        mock_port_client.get_integration_cursor.assert_called_once_with(
            "pull-request", 1
        )


class TestCursorStoreSave:
    async def test_delegates_to_upsert(
        self,
        cursor_store: CursorStore,
        mock_port_client: MagicMock,
        cursor: datetime,
    ) -> None:
        await cursor_store.save("issue", 0, cursor)
        mock_port_client.upsert_integration_cursor.assert_called_once_with(
            "issue", 0, cursor
        )

    async def test_save_different_index(
        self,
        cursor_store: CursorStore,
        mock_port_client: MagicMock,
        cursor: datetime,
    ) -> None:
        await cursor_store.save("build", 2, cursor)
        mock_port_client.upsert_integration_cursor.assert_called_once_with(
            "build", 2, cursor
        )
