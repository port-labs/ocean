from unittest.mock import AsyncMock, patch

import httpx
import pytest

from port_ocean.core.integrations.mixins.lakehouse_buffer import LakehouseBuffer


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
