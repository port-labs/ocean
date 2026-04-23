import pytest
from unittest.mock import AsyncMock
from typing import Any, AsyncGenerator

import port_ocean.context.ocean as ocean_context
from port_ocean.helpers.async_client import (
    OceanAsyncClient,
    SqliteStreamingClientWrapper,
    StreamingClientWrapper,
)
from port_ocean.helpers.stream import Stream


class MockStream:
    """A mock of the port_ocean.helpers.stream.Stream class for testing."""

    def __init__(self, data_chunks: list[list[dict[str, Any]]]) -> None:
        self._data_chunks = data_chunks

    async def get_json_stream(self, target_items: str) -> AsyncGenerator[Any, None]:
        """An async generator that yields the data chunks."""
        for chunk in self._data_chunks:
            yield chunk


@pytest.mark.asyncio
async def test_stream_json_with_streaming_enabled() -> None:
    """
    Tests that when streaming is enabled, the wrapper uses the `get_stream` method
    and yields data in batches.
    """
    # Arrange
    mock_client = AsyncMock(spec=OceanAsyncClient)
    # Simulate receiving the data in two separate chunks/batches
    mock_stream_instance = MockStream(
        [[{"id": 1, "name": "one"}], [{"id": 2, "name": "two"}]]
    )
    mock_client.get_stream.return_value = mock_stream_instance

    wrapper = StreamingClientWrapper(http_client=mock_client)

    # Act
    results = [item async for item in wrapper.stream_json("http://test.com", "results")]

    # Assert
    mock_client.get_stream.assert_called_once_with("http://test.com")
    mock_client.get.assert_not_called()
    assert results == [[{"id": 1, "name": "one"}], [{"id": 2, "name": "two"}]]


@pytest.mark.asyncio
async def test_stream_json_with_empty_results_streaming() -> None:
    """
    Tests that the wrapper handles an empty stream correctly in streaming mode.
    """
    # Arrange
    mock_client = AsyncMock(spec=OceanAsyncClient)
    mock_stream_instance = MockStream([[]])  # Stream yields one empty batch
    mock_client.get_stream.return_value = mock_stream_instance

    wrapper = StreamingClientWrapper(http_client=mock_client)

    # Act
    results = [item async for item in wrapper.stream_json("http://test.com", "results")]

    # Assert
    assert results == [[]]


@pytest.mark.asyncio
async def test_stream_json_path_adaptation_for_streaming() -> None:
    """
    Tests that the wrapper correctly adapts the `target_items_path` for the
    streaming parser (ijson) by appending `.item`.
    """
    # Arrange
    mock_client = AsyncMock(spec=OceanAsyncClient)
    mock_stream = AsyncMock(spec=Stream)
    mock_client.get_stream.return_value = mock_stream

    wrapper = StreamingClientWrapper(http_client=mock_client)

    # Act
    # We only need to trigger the call to check the arguments
    _ = [item async for item in wrapper.stream_json("http://test.com", "results")]

    # Assert
    # Verify that get_json_stream was called with the modified path
    mock_stream.get_json_stream.assert_called_once_with(target_items="results.item")


class MockResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.closed = False

    async def aiter_bytes(
        self, chunk_size: int | None = None
    ) -> AsyncGenerator[Any, None]:
        _ = chunk_size
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_sqlite_stream_json_uses_selected_columns_and_endpoint_override(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ocean_context.ocean.config.streaming, "location", str(tmp_path), raising=False
    )
    payload = b'{"items":[{"id":1,"owner":{"login":"alice"}},{"id":2,"owner":{"login":"bob"}}]}'
    response = MockResponse([payload[:20], payload[20:]])
    mock_client = AsyncMock(spec=OceanAsyncClient)
    mock_client.get_stream.return_value = type("MockHttpStream", (), {"response": response})()
    wrapper = SqliteStreamingClientWrapper(http_client=mock_client)

    results = [
        batch
        async for batch in wrapper.stream_json(
            url="http://test.com/v1/resources",
            target_items_path="items",
            selected_columns=["id", "owner.login"],
            endpoint_path_override="/v1/resources",
            output_batch_size=2,
        )
    ]

    assert results == [
        [{"id": "1", "owner.login": "alice"}, {"id": "2", "owner.login": "bob"}]
    ]
    mock_client.get_stream.assert_called_once_with("http://test.com/v1/resources")
