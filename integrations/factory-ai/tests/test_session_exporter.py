from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from factory_ai.core.exporters.session import SessionExporter
from factory_ai.core.exporters.session.models import (
    GetSessionOptions,
    ListSessionOptions,
    ListSessionsResponse,
    Session,
)


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.factory.ai/api/v0/sessions")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"HTTP {status_code}", request=request, response=response
    )


_MIN_SESSION = {
    "sessionId": "sess-1",
    "title": "Ship the mapper",
    "status": "running",
    "messageCount": 4,
    "createdAt": 1_700_000_000_000,
    "updatedAt": 1_700_000_100_000,
    "computerId": "comp-1",
    "sessionSettings": {
        "model": "claude-sonnet",
        "interactionMode": "auto",
        "autonomyLevel": "medium",
        "worktree": {"repoRoot": "/home/droid/repo"},
    },
    "factoryCredits": 1.5,
}


@pytest.mark.asyncio
async def test_session_exporter_lists_via_typed_response() -> None:
    client_mock = MagicMock()
    response = ListSessionsResponse.model_validate(
        {
            "sessions": [_MIN_SESSION],
            "pagination": {"hasMore": False, "nextCursor": None},
        }
    )
    client_mock.get = AsyncMock(return_value=response)
    exporter = SessionExporter(client_mock)

    batches = [
        batch async for batch in exporter.get_paginated_resources(ListSessionOptions())
    ]

    assert len(batches) == 1
    assert batches[0][0]["sessionId"] == "sess-1"
    assert batches[0][0]["computerId"] == "comp-1"
    assert batches[0][0]["sessionSettings"]["interactionMode"] == "auto"
    client_mock.get.assert_awaited_once_with(
        "/api/v0/sessions",
        ListSessionsResponse,
        params={"limit": "100"},
    )


@pytest.mark.asyncio
async def test_session_exporter_follows_cursor_pagination() -> None:
    client_mock = MagicMock()
    page_1 = ListSessionsResponse.model_validate(
        {
            "sessions": [_MIN_SESSION],
            "pagination": {"hasMore": True, "nextCursor": "cursor-2"},
        }
    )
    page_2 = ListSessionsResponse.model_validate(
        {
            "sessions": [
                {
                    "sessionId": "sess-2",
                    "status": "idle",
                    "messageCount": 0,
                    "createdAt": 1_700_000_200_000,
                    "updatedAt": 1_700_000_200_000,
                    "parent_session_id": "sess-1",
                }
            ],
            "pagination": {"hasMore": False, "nextCursor": None},
        }
    )
    client_mock.get = AsyncMock(side_effect=[page_1, page_2])
    exporter = SessionExporter(client_mock)

    batches = [
        batch async for batch in exporter.get_paginated_resources(ListSessionOptions())
    ]

    assert len(batches) == 2
    assert batches[0][0]["sessionId"] == "sess-1"
    assert batches[1][0]["sessionId"] == "sess-2"
    assert batches[1][0]["parent_session_id"] == "sess-1"
    assert client_mock.get.await_count == 2
    assert client_mock.get.await_args_list[0].kwargs["params"] == {"limit": "100"}
    assert client_mock.get.await_args_list[1].kwargs["params"] == {
        "limit": "100",
        "cursor": "cursor-2",
    }


@pytest.mark.asyncio
async def test_session_exporter_forwards_computer_id_filter() -> None:
    client_mock = MagicMock()
    client_mock.get = AsyncMock(
        return_value=ListSessionsResponse.model_validate(
            {"sessions": [], "pagination": {"hasMore": False, "nextCursor": None}}
        )
    )
    exporter = SessionExporter(client_mock)

    [
        batch
        async for batch in exporter.get_paginated_resources(
            ListSessionOptions(computer_id="comp-9")
        )
    ]

    client_mock.get.assert_awaited_once_with(
        "/api/v0/sessions",
        ListSessionsResponse,
        params={"limit": "100", "computerId": "comp-9"},
    )


@pytest.mark.asyncio
async def test_session_exporter_get_resource() -> None:
    client_mock = MagicMock()
    client_mock.get_or_none = AsyncMock(
        return_value=Session.model_validate(_MIN_SESSION)
    )
    exporter = SessionExporter(client_mock)

    result = await exporter.get_resource(GetSessionOptions(session_id="sess-1"))

    assert result is not None
    assert result["sessionId"] == "sess-1"
    assert result["title"] == "Ship the mapper"
    client_mock.get_or_none.assert_awaited_once_with(
        "/api/v0/sessions/sess-1",
        Session,
        params=None,
    )


@pytest.mark.asyncio
async def test_session_exporter_get_resource_with_computer_id() -> None:
    client_mock = MagicMock()
    client_mock.get_or_none = AsyncMock(
        return_value=Session.model_validate(_MIN_SESSION)
    )
    exporter = SessionExporter(client_mock)

    result = await exporter.get_resource(
        GetSessionOptions(session_id="sess-1", computer_id="comp-1")
    )

    assert result is not None
    client_mock.get_or_none.assert_awaited_once_with(
        "/api/v0/sessions/sess-1",
        Session,
        params={"computerId": "comp-1"},
    )


@pytest.mark.asyncio
async def test_session_exporter_get_resource_not_found() -> None:
    client_mock = MagicMock()
    client_mock.get_or_none = AsyncMock(return_value=None)
    exporter = SessionExporter(client_mock)

    result = await exporter.get_resource(GetSessionOptions(session_id="missing"))

    assert result is None


@pytest.mark.asyncio
async def test_session_exporter_lists_soft_fails_on_403() -> None:
    client_mock = MagicMock()
    client_mock.get = AsyncMock(side_effect=_http_status_error(403))
    exporter = SessionExporter(client_mock)

    batches = [
        batch async for batch in exporter.get_paginated_resources(ListSessionOptions())
    ]

    assert batches == []
    client_mock.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_exporter_lists_rethrows_non_403() -> None:
    client_mock = MagicMock()
    client_mock.get = AsyncMock(side_effect=_http_status_error(500))
    exporter = SessionExporter(client_mock)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        [
            batch
            async for batch in exporter.get_paginated_resources(ListSessionOptions())
        ]

    assert exc_info.value.response is not None
    assert exc_info.value.response.status_code == 500


@pytest.mark.asyncio
async def test_session_exporter_get_resource_soft_fails_on_403() -> None:
    client_mock = MagicMock()
    client_mock.get_or_none = AsyncMock(side_effect=_http_status_error(403))
    exporter = SessionExporter(client_mock)

    result = await exporter.get_resource(GetSessionOptions(session_id="sess-1"))

    assert result is None
