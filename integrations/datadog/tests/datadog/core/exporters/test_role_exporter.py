from datetime import datetime, timezone
from typing import Any, Iterator
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from datadog.client import DatadogClient
from datadog.core.exporters.base_exporter import (
    CHANGED_RESOURCES_FETCH_BATCH_SIZE,
    MAX_PAGE_SIZE,
)
from datadog.core.exporters import RoleExporter
from datadog.core.exporters.role_exporter import (
    GetRoleOptions,
    ListRoleOptions,
)
from datadog.incremental import (
    CHANGED_ROLE_MEMBERSHIPS_AUDIT_QUERY,
    CHANGED_ROLES_AUDIT_QUERY,
)


@pytest.mark.asyncio
async def test_get_roles(mock_datadog_client: DatadogClient) -> None:
    roles_response: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "roles"}, {"id": "2", "type": "roles"}]
    }
    empty_response: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [roles_response, empty_response]

        exporter = RoleExporter(mock_datadog_client)
        roles = []
        async for role_batch in exporter.get_paginated_resources(ListRoleOptions()):
            roles.extend(role_batch)

        assert len(roles) == 2
        assert roles == roles_response["data"]
        mock_request.assert_any_call(
            f"{mock_datadog_client.api_url}/api/v2/roles",
            params={"page[size]": MAX_PAGE_SIZE, "page[number]": 0},
        )


@pytest.mark.asyncio
async def test_get_roles_multiple_pages(mock_datadog_client: DatadogClient) -> None:
    first_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "roles"}]
    }
    second_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "2", "type": "roles"}]
    }
    third_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "3", "type": "roles"}]
    }
    empty_page: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [first_page, second_page, third_page, empty_page]

        exporter = RoleExporter(mock_datadog_client)
        roles = []
        async for role_batch in exporter.get_paginated_resources(ListRoleOptions()):
            roles.extend(role_batch)

        assert len(roles) == 3
        assert roles == first_page["data"] + second_page["data"] + third_page["data"]
        assert mock_request.call_count == 4


@pytest.mark.asyncio
async def test_get_roles_without_enrichment_does_not_fetch_users(
    mock_datadog_client: DatadogClient,
) -> None:
    roles_response: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "role1", "type": "roles"}]
    }
    empty_roles: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [roles_response, empty_roles]

        exporter = RoleExporter(mock_datadog_client)
        roles = []
        async for role_batch in exporter.get_paginated_resources(ListRoleOptions()):
            roles.extend(role_batch)

        assert len(roles) == 1
        assert "__users" not in roles[0]
        # Only the two role-listing requests, no per-role user requests.
        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_get_roles_with_users(mock_datadog_client: DatadogClient) -> None:
    roles_response: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "role1", "type": "roles"}]
    }
    empty_roles: dict[str, list[dict[str, Any]]] = {"data": []}
    users_response: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "users"}, {"id": "2", "type": "users"}]
    }
    empty_users: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            roles_response,
            users_response,
            empty_users,
            empty_roles,
        ]

        exporter = RoleExporter(mock_datadog_client)
        roles = []
        async for role_batch in exporter.get_paginated_resources(
            ListRoleOptions(enrich_with_users=True)
        ):
            roles.extend(role_batch)

        assert len(roles) == 1
        assert roles[0]["__users"] == users_response["data"]


@pytest.mark.asyncio
async def test_enrich_role_with_users(mock_datadog_client: DatadogClient) -> None:
    role_batch = [
        {"id": "role1", "attributes": {"name": "Admin"}},
        {"id": "role2", "attributes": {"name": "Standard"}},
    ]
    role1_users = [{"id": "1", "type": "users"}]
    role2_users = [{"id": "2", "type": "users"}, {"id": "3", "type": "users"}]

    exporter = RoleExporter(mock_datadog_client)
    with patch.object(
        exporter, "_fetch_users_for_role", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = [role1_users, role2_users]

        result = await exporter.enrich_role_with_users(role_batch)

        assert result[0]["__users"] == role1_users
        assert result[1]["__users"] == role2_users
        assert mock_fetch.call_count == 2
        mock_fetch.assert_any_call("role1")
        mock_fetch.assert_any_call("role2")


@pytest.mark.asyncio
async def test_enrich_role_with_users_handles_fetch_error(
    mock_datadog_client: DatadogClient,
) -> None:
    role_batch = [
        {"id": "role1", "attributes": {"name": "Admin"}},
        {"id": "role2", "attributes": {"name": "Standard"}},
    ]
    role2_users = [{"id": "2", "type": "users"}]

    exporter = RoleExporter(mock_datadog_client)
    with patch.object(
        exporter, "_fetch_users_for_role", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = [Exception("boom"), role2_users]

        result = await exporter.enrich_role_with_users(role_batch)

        # Failed role falls back to an empty list, others are unaffected.
        assert result[0]["__users"] == []
        assert result[1]["__users"] == role2_users


@pytest.mark.asyncio
async def test_fetch_users_for_role_paginates(
    mock_datadog_client: DatadogClient,
) -> None:
    first_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "users"}]
    }
    second_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "2", "type": "users"}]
    }
    empty_page: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [first_page, second_page, empty_page]

        exporter = RoleExporter(mock_datadog_client)
        users = await exporter._fetch_users_for_role("role1")

        assert users == first_page["data"] + second_page["data"]
        mock_request.assert_any_call(
            f"{mock_datadog_client.api_url}/api/v2/roles/role1/users",
            params={"page[size]": MAX_PAGE_SIZE, "page[number]": 0},
        )


@pytest.mark.asyncio
async def test_get_resource(mock_datadog_client: DatadogClient) -> None:
    role = {"id": "role1", "type": "roles", "attributes": {"name": "Admin"}}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"data": role}

        exporter = RoleExporter(mock_datadog_client)
        result = await exporter.get_resource(GetRoleOptions(resource_id="role1"))

        assert result == role
        mock_request.assert_called_once_with(
            f"{mock_datadog_client.api_url}/api/v2/roles/role1"
        )


AUDIT_SEARCH_URL = "https://api.datadoghq.com/api/v2/audit/events/search"
SINCE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def _role_event(role_id: str) -> dict[str, Any]:
    return {
        "id": f"event-{role_id}",
        "attributes": {"attributes": {"asset": {"id": role_id, "type": "role"}}},
    }


def _membership_event(role_id: str) -> dict[str, Any]:
    # Asset type is "user", but the asset ID is the role's ID
    return {
        "id": f"membership-event-{role_id}",
        "attributes": {
            "attributes": {
                "asset": {"id": role_id, "type": "user"},
                "http": {"url_details": {"path": f"/api/v2/roles/{role_id}/users"}},
            }
        },
    }


def _audit_page(*events: dict[str, Any], after: str | None = None) -> dict[str, Any]:
    return {"data": list(events), "meta": {"page": {"after": after} if after else {}}}


def _role(role_id: str) -> dict[str, Any]:
    return {"id": role_id, "type": "roles"}


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.datadoghq.com/api/v2/roles/1")
    return httpx.HTTPStatusError(
        "error", request=request, response=httpx.Response(status, request=request)
    )


def _search_query(mock_request: AsyncMock, call: int) -> str:
    return mock_request.call_args_list[call].kwargs["json_data"]["filter"]["query"]


async def _collect_changed(
    exporter: RoleExporter, options: ListRoleOptions = ListRoleOptions()
) -> list[dict[str, Any]]:
    roles: list[dict[str, Any]] = []
    async for batch in exporter.get_changed_roles(options, incremental_cursor=SINCE):
        roles.extend(batch)
    return roles


@pytest.fixture
def role_audit_mocks(
    mock_datadog_client: DatadogClient,
) -> Iterator[tuple[AsyncMock, AsyncMock]]:
    """Patch the audit search request and the per-role fetch.

    By default every fetched role exists.
    """
    with (
        patch.object(
            mock_datadog_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(
            RoleExporter, "get_resource", new_callable=AsyncMock
        ) as mock_get_resource,
    ):
        mock_get_resource.side_effect = lambda options: _role(options.resource_id)
        yield mock_request, mock_get_resource


@pytest.mark.asyncio
async def test_get_changed_roles_searches_audit_events_since_cursor(
    mock_datadog_client: DatadogClient,
    role_audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, _ = role_audit_mocks
    mock_request.return_value = _audit_page()

    assert await _collect_changed(RoleExporter(mock_datadog_client)) == []

    mock_request.assert_called_once_with(
        AUDIT_SEARCH_URL,
        json_data={
            "filter": {
                "query": CHANGED_ROLES_AUDIT_QUERY,
                "from": "2026-11-05T10:00:00+00:00",
                "to": "now",
            },
            "sort": "-timestamp",
            "page": {"limit": MAX_PAGE_SIZE},
        },
        method="POST",
    )


@pytest.mark.asyncio
async def test_get_changed_roles_follows_cursor_and_dedupes(
    mock_datadog_client: DatadogClient,
    role_audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = role_audit_mocks
    mock_request.side_effect = [
        _audit_page(_role_event("1"), _role_event("1"), after="next"),
        _audit_page(_role_event("1"), _role_event("2")),
    ]

    roles = await _collect_changed(RoleExporter(mock_datadog_client))

    assert roles == [_role("1"), _role("2")]
    assert mock_get_resource.await_count == 2
    second_body = mock_request.call_args_list[1].kwargs["json_data"]
    assert second_body["page"] == {"limit": MAX_PAGE_SIZE, "cursor": "next"}


@pytest.mark.asyncio
async def test_get_changed_roles_yields_one_batch_per_concurrent_fetch(
    mock_datadog_client: DatadogClient,
    role_audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, _ = role_audit_mocks
    role_ids = [str(i) for i in range(CHANGED_RESOURCES_FETCH_BATCH_SIZE + 1)]
    mock_request.return_value = _audit_page(*(_role_event(i) for i in role_ids))

    batches = [
        batch
        async for batch in RoleExporter(mock_datadog_client).get_changed_roles(
            ListRoleOptions(), incremental_cursor=SINCE
        )
    ]

    assert [len(batch) for batch in batches] == [CHANGED_RESOURCES_FETCH_BATCH_SIZE, 1]
    assert [role for batch in batches for role in batch] == [_role(i) for i in role_ids]


@pytest.mark.asyncio
async def test_get_changed_roles_includes_membership_changes_when_enriching_users(
    mock_datadog_client: DatadogClient,
    role_audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = role_audit_mocks
    mock_request.side_effect = [
        _audit_page(_role_event("1")),
        _audit_page(_membership_event("1"), _membership_event("2")),
    ]

    roles = await _collect_changed(
        RoleExporter(mock_datadog_client), ListRoleOptions(enrich_with_users=True)
    )

    assert roles == [_role("1"), _role("2")]
    assert _search_query(mock_request, 0) == CHANGED_ROLES_AUDIT_QUERY
    assert _search_query(mock_request, 1) == CHANGED_ROLE_MEMBERSHIPS_AUDIT_QUERY
    mock_get_resource.assert_any_await(
        GetRoleOptions(resource_id="2", enrich_with_users=True)
    )


@pytest.mark.asyncio
async def test_get_changed_roles_skips_membership_changes_without_enriching_users(
    mock_datadog_client: DatadogClient,
    role_audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = role_audit_mocks
    mock_request.return_value = _audit_page(_role_event("1"))

    roles = await _collect_changed(RoleExporter(mock_datadog_client))

    assert roles == [_role("1")]
    mock_request.assert_called_once()
    mock_get_resource.assert_awaited_once_with(
        GetRoleOptions(resource_id="1", enrich_with_users=False)
    )


@pytest.mark.asyncio
async def test_get_changed_roles_skips_roles_that_no_longer_exist(
    mock_datadog_client: DatadogClient,
    role_audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = role_audit_mocks
    mock_request.return_value = _audit_page(_role_event("1"), _role_event("2"))
    mock_get_resource.side_effect = [_http_error(404), _role("2")]

    roles = await _collect_changed(RoleExporter(mock_datadog_client))

    assert roles == [_role("2")]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 500])
async def test_get_changed_roles_raises_other_fetch_errors(
    mock_datadog_client: DatadogClient,
    role_audit_mocks: tuple[AsyncMock, AsyncMock],
    status: int,
) -> None:
    mock_request, mock_get_resource = role_audit_mocks
    mock_request.return_value = _audit_page(_role_event("1"), _role_event("2"))
    mock_get_resource.side_effect = [_http_error(status), _role("2")]

    with pytest.raises(httpx.HTTPStatusError):
        await _collect_changed(RoleExporter(mock_datadog_client))
