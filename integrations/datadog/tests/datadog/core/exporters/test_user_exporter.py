from datetime import datetime, timezone
from typing import Any, Iterator
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from datadog.client import DatadogClient
from datadog.core.exporters.base_exporter import MAX_PAGE_SIZE
from datadog.core.exporters import UserExporter
from datadog.core.exporters.user_exporter import (
    CHANGED_USERS_AUDIT_QUERY,
    GetUserOptions,
)


@pytest.mark.asyncio
async def test_get_users(mock_datadog_client: DatadogClient) -> None:
    users_response: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "users"}, {"id": "2", "type": "users"}]
    }
    empty_response: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [users_response, empty_response]

        exporter = UserExporter(mock_datadog_client)
        users = []
        async for user_batch in exporter.get_paginated_resources():
            users.extend(user_batch)

        assert len(users) == 2
        assert users == users_response["data"]
        mock_request.assert_any_call(
            f"{mock_datadog_client.api_url}/api/v2/users",
            params={"page[size]": MAX_PAGE_SIZE, "page[number]": 0},
        )


@pytest.mark.asyncio
async def test_get_users_multiple_pages(mock_datadog_client: DatadogClient) -> None:
    first_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "users"}]
    }
    second_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "2", "type": "users"}]
    }
    third_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "3", "type": "users"}]
    }
    empty_page: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [first_page, second_page, third_page, empty_page]

        exporter = UserExporter(mock_datadog_client)
        users = []
        async for user_batch in exporter.get_paginated_resources():
            users.extend(user_batch)

        assert len(users) == 3
        assert users == first_page["data"] + second_page["data"] + third_page["data"]
        assert mock_request.call_count == 4


AUDIT_SEARCH_URL = "https://api.datadoghq.com/api/v2/audit/events/search"
SINCE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def _audit_event(user_id: str, path: str = "/api/v2/users") -> dict[str, Any]:
    return {
        "id": f"event-{user_id}",
        "attributes": {
            "attributes": {
                "asset": {"type": "user", "id": user_id},
                "http": {"url_details": {"path": path}},
            }
        },
    }


def _audit_page(*events: dict[str, Any], after: str | None = None) -> dict[str, Any]:
    return {"data": list(events), "meta": {"page": {"after": after} if after else {}}}


def _user(user_id: str) -> dict[str, Any]:
    return {"id": user_id, "type": "users"}


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.datadoghq.com/api/v2/users/1")
    return httpx.HTTPStatusError(
        "error", request=request, response=httpx.Response(status, request=request)
    )


async def _collect(exporter: UserExporter) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    async for batch in exporter.get_changed_users(since=SINCE):
        users.extend(batch)
    return users


@pytest.fixture
def audit_mocks(
    mock_datadog_client: DatadogClient,
) -> Iterator[tuple[AsyncMock, AsyncMock]]:
    """Patch the audit search request and the per-user fetch.

    By default every fetched user exists.
    """
    with (
        patch.object(
            mock_datadog_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(
            UserExporter, "get_resource", new_callable=AsyncMock
        ) as mock_get_resource,
    ):
        mock_get_resource.side_effect = lambda options: _user(options.resource_id)
        yield mock_request, mock_get_resource


@pytest.mark.asyncio
async def test_get_changed_users_searches_audit_events_since_cursor(
    mock_datadog_client: DatadogClient,
    audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, _ = audit_mocks
    mock_request.return_value = _audit_page()

    await _collect(UserExporter(mock_datadog_client))

    mock_request.assert_called_once_with(
        AUDIT_SEARCH_URL,
        json_data={
            "filter": {
                "query": CHANGED_USERS_AUDIT_QUERY,
                "from": "2026-11-05T10:00:00+00:00",
                "to": "now",
            },
            "sort": "-timestamp",
            "page": {"limit": MAX_PAGE_SIZE},
        },
        method="POST",
    )


def test_changed_users_query_matches_created_or_modified_users() -> None:
    assert CHANGED_USERS_AUDIT_QUERY == (
        '@evt.name:"Access Management" @asset.type:user @action:(created OR modified)'
    )


@pytest.mark.asyncio
async def test_get_changed_users_follows_cursor_and_dedupes(
    mock_datadog_client: DatadogClient,
    audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = audit_mocks
    mock_request.side_effect = [
        _audit_page(_audit_event("1"), _audit_event("2"), after="next"),
        _audit_page(_audit_event("2"), _audit_event("3")),
    ]

    users = await _collect(UserExporter(mock_datadog_client))

    assert users == [_user("1"), _user("2"), _user("3")]
    assert mock_get_resource.await_count == 3
    second_body = mock_request.call_args_list[1].kwargs["json_data"]
    assert second_body["page"] == {"limit": MAX_PAGE_SIZE, "cursor": "next"}


@pytest.mark.asyncio
async def test_get_changed_users_skips_role_membership_events(
    mock_datadog_client: DatadogClient,
    audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = audit_mocks
    mock_request.return_value = _audit_page(
        _audit_event("1", path="/api/v2/roles/admin/users"), _audit_event("2")
    )

    users = await _collect(UserExporter(mock_datadog_client))

    assert users == [_user("2")]
    mock_get_resource.assert_awaited_once_with(GetUserOptions(resource_id="2"))


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 500])
async def test_get_changed_users_skips_users_that_fail_to_fetch(
    mock_datadog_client: DatadogClient,
    audit_mocks: tuple[AsyncMock, AsyncMock],
    status: int,
) -> None:
    mock_request, mock_get_resource = audit_mocks
    mock_request.return_value = _audit_page(_audit_event("1"), _audit_event("2"))
    mock_get_resource.side_effect = [_http_error(status), _user("2")]

    users = await _collect(UserExporter(mock_datadog_client))

    assert users == [_user("2")]
