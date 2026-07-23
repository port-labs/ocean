from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clients.endpoints import V1_AGENTS, v1_agent_runs
from core.exporters.agents_exporter import AgentsExporter
from core.exporters.runs_exporter import RunsExporter


async def _aiter(
    batches: list[list[dict[str, Any]]]
) -> AsyncGenerator[list[dict[str, Any]], None]:
    for batch in batches:
        yield batch


@pytest.mark.asyncio
async def test_agents_exporter_yields_batches_from_v1_list_agents() -> None:
    client_mock = MagicMock()
    client_mock.paginate_by_cursor.return_value = _aiter(
        [[{"id": "bc-1"}, {"id": "bc-2"}], [{"id": "bc-3"}]]
    )
    exporter = AgentsExporter(client_mock)

    batches = [batch async for batch in exporter.get_paginated_resources()]

    assert batches == [[{"id": "bc-1"}, {"id": "bc-2"}], [{"id": "bc-3"}]]
    client_mock.paginate_by_cursor.assert_called_once_with(
        V1_AGENTS, "items", params={"includeArchived": False}
    )


@pytest.mark.asyncio
async def test_agents_exporter_forwards_include_archived() -> None:
    client_mock = MagicMock()
    client_mock.paginate_by_cursor.return_value = _aiter([])
    exporter = AgentsExporter(client_mock)

    [batch async for batch in exporter.get_paginated_resources(include_archived=True)]

    client_mock.paginate_by_cursor.assert_called_once_with(
        V1_AGENTS, "items", params={"includeArchived": True}
    )


@pytest.mark.asyncio
async def test_runs_exporter_fans_out_list_runs_per_agent() -> None:
    client_mock = MagicMock()

    def _paginate(
        path: str, items_key: str, params: dict[str, Any] | None = None, **_: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if path == V1_AGENTS:
            return _aiter([[{"id": "bc-1"}, {"id": "bc-2"}]])
        if path == v1_agent_runs("bc-1"):
            return _aiter([[{"id": "run-1", "agentId": "bc-1"}]])
        if path == v1_agent_runs("bc-2"):
            return _aiter([[{"id": "run-2", "agentId": "bc-2"}]])
        return _aiter([])

    client_mock.paginate_by_cursor.side_effect = _paginate
    client_mock.send_api_request = AsyncMock(return_value={"runs": []})
    exporter = RunsExporter(client_mock)

    batches = [batch async for batch in exporter.get_paginated_resources()]

    assert batches == [
        [{"id": "run-1", "agentId": "bc-1"}],
        [{"id": "run-2", "agentId": "bc-2"}],
    ]
    assert client_mock.paginate_by_cursor.call_count == 3


@pytest.mark.asyncio
async def test_runs_exporter_forwards_include_archived() -> None:
    client_mock = MagicMock()
    client_mock.paginate_by_cursor.return_value = _aiter([])
    exporter = RunsExporter(client_mock)

    [batch async for batch in exporter.get_paginated_resources(include_archived=True)]

    client_mock.paginate_by_cursor.assert_called_once_with(
        V1_AGENTS, "items", params={"includeArchived": True}
    )


@pytest.mark.asyncio
async def test_runs_exporter_skips_agents_without_id() -> None:
    client_mock = MagicMock()
    client_mock.paginate_by_cursor.return_value = _aiter([[{"name": "no id"}]])
    exporter = RunsExporter(client_mock)

    batches = [batch async for batch in exporter.get_paginated_resources()]

    assert batches == []
    assert client_mock.paginate_by_cursor.call_count == 1


@pytest.mark.asyncio
async def test_runs_exporter_skips_empty_batches() -> None:
    client_mock = MagicMock()

    def _paginate(
        path: str, items_key: str, params: dict[str, Any] | None = None, **_: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if path == V1_AGENTS:
            return _aiter([[{"id": "bc-1"}]])
        return _aiter([[]])

    client_mock.paginate_by_cursor.side_effect = _paginate
    client_mock.send_api_request = AsyncMock(return_value={"runs": []})
    exporter = RunsExporter(client_mock)

    batches = [batch async for batch in exporter.get_paginated_resources()]

    assert batches == []


@pytest.mark.asyncio
async def test_runs_exporter_merges_usage_into_matching_run() -> None:
    client_mock = MagicMock()

    def _paginate(
        path: str, items_key: str, params: dict[str, Any] | None = None, **_: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if path == V1_AGENTS:
            return _aiter([[{"id": "bc-1"}]])
        return _aiter(
            [[{"id": "run-1", "agentId": "bc-1"}, {"id": "run-2", "agentId": "bc-1"}]]
        )

    client_mock.paginate_by_cursor.side_effect = _paginate
    client_mock.send_api_request = AsyncMock(
        return_value={
            "totalUsage": {"totalTokens": 300},
            "runs": [
                {"id": "run-1", "usage": {"totalTokens": 100}},
                {"id": "run-2", "usage": {"totalTokens": 200}},
            ],
        }
    )
    exporter = RunsExporter(client_mock)

    batches = [batch async for batch in exporter.get_paginated_resources()]

    assert batches == [
        [
            {
                "id": "run-1",
                "agentId": "bc-1",
                "usage": {"totalTokens": 100},
            },
            {
                "id": "run-2",
                "agentId": "bc-1",
                "usage": {"totalTokens": 200},
            },
        ]
    ]


@pytest.mark.asyncio
async def test_runs_exporter_continues_when_usage_fetch_fails() -> None:
    client_mock = MagicMock()

    def _paginate(
        path: str, items_key: str, params: dict[str, Any] | None = None, **_: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if path == V1_AGENTS:
            return _aiter([[{"id": "bc-1"}]])
        return _aiter([[{"id": "run-1", "agentId": "bc-1"}]])

    client_mock.paginate_by_cursor.side_effect = _paginate
    client_mock.send_api_request = AsyncMock(side_effect=RuntimeError("boom"))
    exporter = RunsExporter(client_mock)

    batches = [batch async for batch in exporter.get_paginated_resources()]

    assert batches == [[{"id": "run-1", "agentId": "bc-1"}]]


@pytest.mark.asyncio
async def test_runs_exporter_sets_agent_id_when_missing() -> None:
    client_mock = MagicMock()

    def _paginate(
        path: str, items_key: str, params: dict[str, Any] | None = None, **_: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if path == V1_AGENTS:
            return _aiter([[{"id": "bc-1"}]])
        return _aiter([[{"id": "run-1"}]])

    client_mock.paginate_by_cursor.side_effect = _paginate
    client_mock.send_api_request = AsyncMock(return_value={"runs": []})
    exporter = RunsExporter(client_mock)

    batches = [batch async for batch in exporter.get_paginated_resources()]

    assert batches == [[{"id": "run-1", "agentId": "bc-1"}]]
