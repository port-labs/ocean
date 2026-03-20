import os
from typing import Any, AsyncGenerator

import pytest

from port_ocean.helpers.sqlite_stream import (
    EndpointTableNameResolver,
    JsonColumnProjector,
    SqliteJsonStream,
    SqliteStreamStore,
)


class FakeResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.closed = False

    async def aiter_bytes(
        self, chunk_size: int | None = None
    ) -> AsyncGenerator[bytes, None]:
        _ = chunk_size
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


def test_endpoint_table_name_resolver_returns_safe_deterministic_name() -> None:
    resolver = EndpointTableNameResolver()
    endpoint = "https://api.example.com/v1/my-resource?limit=100"

    first = resolver.resolve(endpoint)
    second = resolver.resolve(endpoint)

    assert first == second
    assert first.startswith("v1_my_resource_")
    assert "?" not in first
    assert "/" not in first


def test_json_column_projector_supports_dot_paths() -> None:
    projector = JsonColumnProjector(["id", "owner.login", "details"])
    item: dict[str, Any] = {
        "id": 7,
        "owner": {"login": "ocean-user"},
        "details": {"enabled": True},
    }

    projected = projector.project(item)

    assert projected["id"] == "7"
    assert projected["owner.login"] == "ocean-user"
    assert projected["details"] == '{"enabled": true}'


@pytest.mark.asyncio
async def test_sqlite_json_stream_yields_batches_and_cleans_temp_db(
    tmp_path: Any,
) -> None:
    payload = b'{"items":[{"id":1,"owner":{"login":"alice"}},{"id":2,"owner":{"login":"bob"}}]}'
    chunks = [payload[:25], payload[25:50], payload[50:]]
    response = FakeResponse(chunks)
    projector = JsonColumnProjector(["id", "owner.login"])
    store = SqliteStreamStore(
        table_name="items_table",
        projector=projector,
        db_directory=str(tmp_path),
    )
    db_path = store.db_path
    stream = SqliteJsonStream(response=response, stream_store=store)  # type: ignore[arg-type]

    results = [
        batch
        async for batch in stream.stream_json(
            target_items="items.item",
            output_batch_size=1,
            max_buffer_size_mb=1,
        )
    ]

    assert results == [
        [{"id": "1", "owner.login": "alice"}],
        [{"id": "2", "owner.login": "bob"}],
    ]
    assert response.closed is True
    assert os.path.exists(db_path) is False
