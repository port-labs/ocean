from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from port_ocean.clients.port.mixins.integrations import IntegrationClientMixin
from port_ocean.core.integrations.mixins.lakehouse_buffer import LakehouseBuffer
from port_ocean.core.models import LakehouseOperation


def _make_buffer(*, fatal: bool = False) -> LakehouseBuffer:
    buffer = LakehouseBuffer(
        sync_id="sync-123",
        kind="file",
        resync_start_time=None,
        fatal=fatal,
    )
    buffer._buffer = [{"items": [{"id": "1"}]}]
    buffer._current_size_bytes = 100
    return buffer


@pytest.mark.asyncio
async def test_flush_non_fatal_swallows_connect_error_and_clears_buffer() -> None:
    buffer = _make_buffer(fatal=False)

    with patch(
        "port_ocean.core.integrations.mixins.lakehouse_buffer.ocean"
    ) as mock_ocean:
        mock_ocean.port_client.post_integration_raw_data_batch = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        await buffer.flush()

    assert buffer._buffer == []
    assert buffer._current_size_bytes == 0
    mock_ocean.port_client.post_integration_raw_data_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_flush_fatal_reraises_connect_error() -> None:
    buffer = _make_buffer(fatal=True)

    with patch(
        "port_ocean.core.integrations.mixins.lakehouse_buffer.ocean"
    ) as mock_ocean:
        mock_ocean.port_client.post_integration_raw_data_batch = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with pytest.raises(httpx.ConnectError):
            await buffer.flush()

    mock_ocean.port_client.post_integration_raw_data_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_handles_datetime_in_items() -> None:
    buffer = LakehouseBuffer(
        sync_id="sync-123",
        kind="file",
        resync_start_time=None,
    )
    entry = {
        "request": {},
        "response": {},
        "metadata": {
            "operation": LakehouseOperation.UPSERT,
            "resource_index": 0,
            "extraction_timestamp": 123,
        },
        "items": [{"id": "1", "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc)}],
    }

    with patch(
        "port_ocean.core.integrations.mixins.lakehouse_buffer.ocean"
    ) as mock_ocean:
        mock_ocean.port_client.post_integration_raw_data_batch = AsyncMock()

        await buffer.add(entry)

    assert buffer._current_size_bytes > 0
    assert len(buffer._buffer) == 1


def _make_port_client_for_flush() -> IntegrationClientMixin:
    auth = MagicMock()
    auth.headers = AsyncMock(return_value={"Authorization": "Bearer test-token"})
    auth.integration_type = "github"

    client = MagicMock()
    client.post = AsyncMock()
    client.post.return_value = MagicMock(status_code=200, is_error=False)

    integration_client = IntegrationClientMixin(
        integration_identifier="test-integration",
        integration_version="1.0.0",
        auth=auth,
        client=client,
    )
    integration_client.get_ingest_attributes = AsyncMock(  # type: ignore[method-assign]
        return_value={"ingestUrl": "https://api.example.com"}
    )
    return integration_client


@pytest.mark.asyncio
async def test_flush_serializes_datetime_in_items() -> None:
    buffer = LakehouseBuffer(
        sync_id="sync-123",
        kind="file",
        resync_start_time=None,
    )
    created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    entry = {
        "request": {},
        "response": {},
        "metadata": {
            "operation": LakehouseOperation.UPSERT,
            "resource_index": 0,
            "extraction_timestamp": 123,
        },
        "items": [{"id": "1", "created_at": created_at}],
    }
    port_client = _make_port_client_for_flush()

    with (
        patch("port_ocean.core.integrations.mixins.lakehouse_buffer.ocean") as mock_ocean,
        patch(
            "port_ocean.clients.port.mixins.integrations.handle_port_status_code"
        ),
    ):
        mock_ocean.port_client = port_client
        await buffer.add(entry)
        await buffer.flush()

    port_client.client.post.assert_awaited_once()
    body: dict[str, Any] = port_client.client.post.call_args.kwargs["json"]
    assert body["data"][0]["items"][0]["created_at"] == created_at.isoformat()
    assert buffer._buffer == []
    assert buffer._current_size_bytes == 0


@pytest.mark.asyncio
async def test_flush_non_fatal_succeeds_normally() -> None:
    buffer = _make_buffer(fatal=False)

    with patch(
        "port_ocean.core.integrations.mixins.lakehouse_buffer.ocean"
    ) as mock_ocean:
        mock_ocean.port_client.post_integration_raw_data_batch = AsyncMock()

        await buffer.flush()

    assert buffer._buffer == []
    assert buffer._current_size_bytes == 0
    mock_ocean.port_client.post_integration_raw_data_batch.assert_awaited_once()
