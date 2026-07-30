from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters.base_exporter import MAX_PAGE_SIZE
from datadog.core.exporters import UserExporter


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
