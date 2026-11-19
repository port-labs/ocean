from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from factory_ai.core.exporters.user import UserExporter
from factory_ai.core.exporters.user.models import (
    GetUserOptions,
    ListUserOptions,
    ListUsersResponse,
)

_MIN_USER = {
    "id": "user_01",
    "email": "ada@example.com",
    "firstName": "Ada",
    "lastName": "Lovelace",
    "createdAt": "2024-01-15T12:00:00.000Z",
    "lastSignInAt": "2024-06-01T09:30:00.000Z",
    "metadata": {},
    "role": "manager",
}


@pytest.mark.asyncio
async def test_user_exporter_lists_via_typed_response() -> None:
    client_mock = MagicMock()
    response = ListUsersResponse.parse_obj(
        {
            "users": [_MIN_USER],
            "pagination": {"hasMore": False, "nextCursor": None},
        }
    )
    client_mock.get = AsyncMock(return_value=response)
    exporter = UserExporter(client_mock)

    batches = [
        batch async for batch in exporter.get_paginated_resources(ListUserOptions())
    ]

    assert len(batches) == 1
    assert batches[0][0]["id"] == "user_01"
    assert batches[0][0]["email"] == "ada@example.com"
    assert batches[0][0]["role"] == "manager"
    client_mock.get.assert_awaited_once_with(
        "/api/v0/organization/users",
        ListUsersResponse,
        params={"limit": "100"},
    )


@pytest.mark.asyncio
async def test_user_exporter_follows_cursor_pagination() -> None:
    client_mock = MagicMock()
    page_1 = ListUsersResponse.parse_obj(
        {
            "users": [_MIN_USER],
            "pagination": {"hasMore": True, "nextCursor": "cursor-2"},
        }
    )
    page_2 = ListUsersResponse.parse_obj(
        {
            "users": [
                {
                    "id": "user_02",
                    "email": "al@example.com",
                    "createdAt": "2024-02-01T00:00:00.000Z",
                    "metadata": {},
                }
            ],
            "pagination": {"hasMore": False, "nextCursor": None},
        }
    )
    client_mock.get = AsyncMock(side_effect=[page_1, page_2])
    exporter = UserExporter(client_mock)

    batches = [
        batch async for batch in exporter.get_paginated_resources(ListUserOptions())
    ]

    assert len(batches) == 2
    assert batches[0][0]["id"] == "user_01"
    assert batches[1][0]["id"] == "user_02"
    assert client_mock.get.await_count == 2
    assert client_mock.get.await_args_list[0].kwargs["params"] == {"limit": "100"}
    assert client_mock.get.await_args_list[1].kwargs["params"] == {
        "limit": "100",
        "cursor": "cursor-2",
    }


@pytest.mark.asyncio
async def test_user_exporter_get_resource_scans_pages() -> None:
    client_mock = MagicMock()
    page_1 = ListUsersResponse.parse_obj(
        {
            "users": [_MIN_USER],
            "pagination": {"hasMore": True, "nextCursor": "cursor-2"},
        }
    )
    page_2 = ListUsersResponse.parse_obj(
        {
            "users": [
                {
                    "id": "user_02",
                    "email": "al@example.com",
                    "createdAt": "2024-02-01T00:00:00.000Z",
                    "metadata": {},
                }
            ],
            "pagination": {"hasMore": False, "nextCursor": None},
        }
    )
    client_mock.get = AsyncMock(side_effect=[page_1, page_2])
    exporter = UserExporter(client_mock)

    result = await exporter.get_resource(GetUserOptions(user_id="user_02"))

    assert result is not None
    assert result["id"] == "user_02"
    assert result["email"] == "al@example.com"


@pytest.mark.asyncio
async def test_user_exporter_get_resource_not_found() -> None:
    client_mock = MagicMock()
    client_mock.get = AsyncMock(
        return_value=ListUsersResponse.parse_obj(
            {
                "users": [_MIN_USER],
                "pagination": {"hasMore": False, "nextCursor": None},
            }
        )
    )
    exporter = UserExporter(client_mock)

    result = await exporter.get_resource(GetUserOptions(user_id="missing"))

    assert result is None
