from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.endpoints import V1_AGENTS, v1_agent_runs
from core.exporters.agents_exporter import AgentsExporter
from core.exporters.runs_exporter import RunsExporter
from core.options import GetRunOptions, ListAgentOptions, ListRunOptions


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
    options = ListAgentOptions()

    batches = [batch async for batch in exporter.get_paginated_resources(options)]

    assert batches == [[{"id": "bc-1"}, {"id": "bc-2"}], [{"id": "bc-3"}]]
    client_mock.paginate_by_cursor.assert_called_once_with(
        V1_AGENTS, "items", params={"includeArchived": False}
    )


@pytest.mark.asyncio
async def test_agents_exporter_forwards_include_archived() -> None:
    client_mock = MagicMock()
    client_mock.paginate_by_cursor.return_value = _aiter([])
    exporter = AgentsExporter(client_mock)
    options = ListAgentOptions(include_archived=True)

    [batch async for batch in exporter.get_paginated_resources(options)]

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
    agents_exporter = AgentsExporter(client_mock)
    with patch.object(
        agents_exporter, "get_runs_usage_map_for_agent", AsyncMock(return_value={})
    ):
        exporter = RunsExporter(client_mock, agents_exporter)

        batches = [
            batch async for batch in exporter.get_paginated_resources(ListRunOptions())
        ]

    assert batches == [
        [{"id": "run-1", "agentId": "bc-1"}],
        [{"id": "run-2", "agentId": "bc-2"}],
    ]
    assert client_mock.paginate_by_cursor.call_count == 3


@pytest.mark.asyncio
async def test_runs_exporter_forwards_include_archived() -> None:
    client_mock = MagicMock()
    client_mock.paginate_by_cursor.return_value = _aiter([])
    agents_exporter = AgentsExporter(client_mock)
    exporter = RunsExporter(client_mock, agents_exporter)

    [
        batch
        async for batch in exporter.get_paginated_resources(
            ListRunOptions(include_archived=True)
        )
    ]

    client_mock.paginate_by_cursor.assert_called_once_with(
        V1_AGENTS, "items", params={"includeArchived": True}
    )


@pytest.mark.asyncio
async def test_runs_exporter_skips_agents_without_id() -> None:
    client_mock = MagicMock()
    client_mock.paginate_by_cursor.return_value = _aiter([[{"name": "no id"}]])
    agents_exporter = AgentsExporter(client_mock)
    exporter = RunsExporter(client_mock, agents_exporter)

    batches = [
        batch async for batch in exporter.get_paginated_resources(ListRunOptions())
    ]

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
    agents_exporter = AgentsExporter(client_mock)
    with patch.object(
        agents_exporter, "get_runs_usage_map_for_agent", AsyncMock(return_value={})
    ):
        exporter = RunsExporter(client_mock, agents_exporter)

        batches = [
            batch async for batch in exporter.get_paginated_resources(ListRunOptions())
        ]

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
    agents_exporter = AgentsExporter(client_mock)
    usage_mock = AsyncMock(
        return_value={
            "run-1": {"totalTokens": 100},
            "run-2": {"totalTokens": 200},
        }
    )
    with patch.object(agents_exporter, "get_runs_usage_map_for_agent", usage_mock):
        exporter = RunsExporter(client_mock, agents_exporter)

        batches = [
            batch async for batch in exporter.get_paginated_resources(ListRunOptions())
        ]

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
async def test_runs_exporter_skips_usage_when_disabled() -> None:
    client_mock = MagicMock()

    def _paginate(
        path: str, items_key: str, params: dict[str, Any] | None = None, **_: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if path == V1_AGENTS:
            return _aiter([[{"id": "bc-1"}]])
        return _aiter([[{"id": "run-1", "agentId": "bc-1"}]])

    client_mock.paginate_by_cursor.side_effect = _paginate
    agents_exporter = AgentsExporter(client_mock)
    usage_mock = AsyncMock()
    with patch.object(agents_exporter, "get_runs_usage_map_for_agent", usage_mock):
        exporter = RunsExporter(client_mock, agents_exporter)

        batches = [
            batch
            async for batch in exporter.get_paginated_resources(
                ListRunOptions(enrich_runs_with_usage=False)
            )
        ]

    assert batches == [[{"id": "run-1", "agentId": "bc-1"}]]
    usage_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_runs_exporter_stops_at_oldest_run_date() -> None:
    client_mock = MagicMock()
    cutoff = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)

    def _paginate(
        path: str, items_key: str, params: dict[str, Any] | None = None, **_: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if path == V1_AGENTS:
            return _aiter([[{"id": "bc-1"}]])
        return _aiter(
            [
                [
                    {
                        "id": "run-new",
                        "agentId": "bc-1",
                        "createdAt": "2025-06-01T13:00:00Z",
                    },
                    {
                        "id": "run-old",
                        "agentId": "bc-1",
                        "createdAt": "2025-06-01T11:00:00Z",
                    },
                ],
                [
                    {
                        "id": "run-older",
                        "agentId": "bc-1",
                        "createdAt": "2025-05-01T11:00:00Z",
                    }
                ],
            ]
        )

    client_mock.paginate_by_cursor.side_effect = _paginate
    agents_exporter = AgentsExporter(client_mock)
    with patch.object(
        agents_exporter, "get_runs_usage_map_for_agent", AsyncMock(return_value={})
    ):
        exporter = RunsExporter(client_mock, agents_exporter)

        batches = [
            batch
            async for batch in exporter.get_paginated_resources(
                ListRunOptions(oldest_run_date=cutoff)
            )
        ]

    assert batches == [
        [
            {
                "id": "run-new",
                "agentId": "bc-1",
                "createdAt": "2025-06-01T13:00:00Z",
            }
        ]
    ]
    assert client_mock.paginate_by_cursor.call_count == 2


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

    async def _send_api_request(
        method: str, path: str, **kwargs: object
    ) -> dict[str, object]:
        if path.endswith("/usage"):
            raise RuntimeError("boom")
        return {}

    client_mock.send_api_request = AsyncMock(side_effect=_send_api_request)
    exporter = RunsExporter(client_mock, AgentsExporter(client_mock))

    batches = [
        batch async for batch in exporter.get_paginated_resources(ListRunOptions())
    ]

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
    agents_exporter = AgentsExporter(client_mock)
    with patch.object(
        agents_exporter, "get_runs_usage_map_for_agent", AsyncMock(return_value={})
    ):
        exporter = RunsExporter(client_mock, agents_exporter)

        batches = [
            batch async for batch in exporter.get_paginated_resources(ListRunOptions())
        ]

    assert batches == [[{"id": "run-1", "agentId": "bc-1"}]]


@pytest.mark.asyncio
async def test_runs_exporter_get_resource_attaches_usage() -> None:
    client_mock = MagicMock()

    async def _send_api_request(
        method: str, path: str, **kwargs: object
    ) -> dict[str, object]:
        if path.endswith("/usage"):
            return {
                "runs": [
                    {
                        "id": "run-1",
                        "usage": {
                            "inputTokens": 10,
                            "outputTokens": 20,
                            "totalTokens": 30,
                        },
                    }
                ]
            }
        return {"id": "run-1", "status": "FINISHED", "agentId": "bc-1"}

    client_mock.send_api_request = AsyncMock(side_effect=_send_api_request)
    exporter = RunsExporter(client_mock, AgentsExporter(client_mock))

    run_raw = await exporter.get_resource(
        GetRunOptions(agent_id="bc-1", run_id="run-1", status="ERROR")
    )

    assert run_raw["status"] == "FINISHED"
    assert run_raw["usage"] == {
        "inputTokens": 10,
        "outputTokens": 20,
        "totalTokens": 30,
    }
    assert client_mock.send_api_request.await_count == 2


@pytest.mark.asyncio
async def test_agents_exporter_get_runs_usage_map_for_agent_ignores_malformed_rows() -> (
    None
):
    client_mock = MagicMock()
    client_mock.send_api_request = AsyncMock(
        return_value={
            "runs": [
                "bad-row",
                {"id": "run-1", "usage": {"totalTokens": 10}},
                {"usage": {"totalTokens": 20}},
            ]
        }
    )
    exporter = AgentsExporter(client_mock)

    usage_by_run_id = await exporter.get_runs_usage_map_for_agent("bc-1")

    assert usage_by_run_id == {"run-1": {"totalTokens": 10}}


@pytest.mark.asyncio
async def test_agents_exporter_get_runs_usage_map_for_agent_returns_empty_when_runs_not_list() -> (
    None
):
    client_mock = MagicMock()
    client_mock.send_api_request = AsyncMock(return_value={"runs": "bad"})
    exporter = AgentsExporter(client_mock)

    usage_by_run_id = await exporter.get_runs_usage_map_for_agent("bc-1")

    assert usage_by_run_id == {}
