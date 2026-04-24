"""Tests for helper utilities"""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Tuple
import pytest

from http_server.helpers.utils import (
    process_endpoints_concurrently,
    DEFAULT_CONCURRENCY_LIMIT,
)


@pytest.mark.asyncio
class TestProcessEndpointsConcurrently:
    """Test concurrent endpoint processing"""

    async def test_processes_multiple_endpoints(self) -> None:
        """Test that multiple endpoints are processed"""
        endpoints = [
            ("/api/teams/1", {"team_id": "1"}),
            ("/api/teams/2", {"team_id": "2"}),
            ("/api/teams/3", {"team_id": "3"}),
        ]

        async def mock_fetch(
            endpoint: str, path_params: Dict[str, str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [{"endpoint": endpoint, "params": path_params}]

        results: List[List[Dict[str, Any]]] = []
        async for batch in process_endpoints_concurrently(
            endpoints=endpoints,
            fetch_fn=mock_fetch,
            concurrency_limit=DEFAULT_CONCURRENCY_LIMIT,
        ):
            results.append(batch)

        assert len(results) == 3
        result_endpoints = {r[0]["endpoint"] for r in results}
        assert result_endpoints == {"/api/teams/1", "/api/teams/2", "/api/teams/3"}

    async def test_empty_endpoints_list(self) -> None:
        """Test handling of empty endpoints list"""
        results: List[List[Dict[str, Any]]] = []

        async def mock_fetch(
            endpoint: str, path_params: Dict[str, str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [{"endpoint": endpoint}]

        async for batch in process_endpoints_concurrently(
            endpoints=[],
            fetch_fn=mock_fetch,
        ):
            results.append(batch)

        assert results == []

    async def test_respects_concurrency_limit(self) -> None:
        """Test that concurrency is properly bounded"""
        concurrency_limit = 3
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        endpoints: List[Tuple[str, Dict[str, str]]] = [
            (f"/api/items/{i}", {}) for i in range(10)
        ]

        async def mock_fetch(
            endpoint: str, path_params: Dict[str, str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            nonlocal max_concurrent, current_concurrent

            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent

            await asyncio.sleep(0.05)
            yield [{"endpoint": endpoint}]

            async with lock:
                current_concurrent -= 1

        results: List[List[Dict[str, Any]]] = []
        async for batch in process_endpoints_concurrently(
            endpoints=endpoints,
            fetch_fn=mock_fetch,
            concurrency_limit=concurrency_limit,
        ):
            results.append(batch)

        assert len(results) == 10
        assert (
            max_concurrent <= concurrency_limit
        ), f"Max concurrent {max_concurrent} exceeded limit {concurrency_limit}"

    async def test_yields_multiple_batches_per_endpoint(self) -> None:
        """Test endpoints that yield multiple batches"""
        endpoints: List[Tuple[str, Dict[str, str]]] = [("/api/items", {})]

        async def mock_fetch(
            endpoint: str, path_params: Dict[str, str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [{"page": 1}]
            yield [{"page": 2}]
            yield [{"page": 3}]

        results: List[List[Dict[str, Any]]] = []
        async for batch in process_endpoints_concurrently(
            endpoints=endpoints,
            fetch_fn=mock_fetch,
        ):
            results.append(batch)

        assert len(results) == 3
        pages = [r[0]["page"] for r in results]
        assert sorted(pages) == [1, 2, 3]
