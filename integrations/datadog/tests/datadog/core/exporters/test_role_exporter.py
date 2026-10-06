from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters.base_exporter import MAX_PAGE_SIZE
from datadog.core.exporters import RoleExporter
from datadog.core.exporters.role_exporter import GetRoleOptions, ListRoleOptions


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
