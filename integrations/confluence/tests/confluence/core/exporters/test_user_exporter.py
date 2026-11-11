from unittest.mock import AsyncMock, MagicMock

import pytest

from confluence.core.exporters.user_exporter import (
    USER_PAGE_SIZE,
    USER_SEARCH_PATH,
    UserExporter,
)
from confluence.core.options import UserExportOptions


def _page(
    users: list[dict[str, str]], total: int, start_size: int | None = None
) -> dict[str, object]:
    return {
        "results": [
            {"user": user, "url": f"/people/{user['accountId']}"} for user in users
        ],
        "size": start_size if start_size is not None else len(users),
        "totalSize": total,
    }


@pytest.mark.asyncio
class TestUserExporter:
    async def test_lists_users_from_search(self) -> None:
        client = MagicMock()
        client.site_url = "https://example.atlassian.net"
        client.send_api_request = AsyncMock(
            side_effect=[
                _page(
                    [{"accountId": "1", "displayName": "Ada"}],
                    total=150,
                    start_size=USER_PAGE_SIZE,
                ),
                _page([{"accountId": "2", "displayName": "Grace"}], total=150),
            ]
        )
        exporter = UserExporter(client)

        batches = [
            batch
            async for batch in exporter.get_paginated_resources(UserExportOptions())
        ]

        assert [user["accountId"] for batch in batches for user in batch] == ["1", "2"]
        assert batches[0][0]["webUrl"] == "https://example.atlassian.net/wiki/people/1"
        first_params = client.send_api_request.await_args_list[0].kwargs["params"]
        assert first_params["cql"] == "type=user"
        assert first_params["sitePermissionTypeFilter"] == "all"
        assert first_params["start"] == 0
        second_params = client.send_api_request.await_args_list[1].kwargs["params"]
        assert second_params["start"] == USER_PAGE_SIZE
        assert client.send_api_request.await_args_list[0].args == (USER_SEARCH_PATH,)

    async def test_permission_filter_is_forwarded(self) -> None:
        client = MagicMock()
        client.site_url = "https://example.atlassian.net"
        client.send_api_request = AsyncMock(return_value=_page([], total=0))
        exporter = UserExporter(client)

        _ = [
            batch
            async for batch in exporter.get_paginated_resources(
                UserExportOptions(site_permission_type="none")
            )
        ]

        params = client.send_api_request.await_args.kwargs["params"]
        assert params["sitePermissionTypeFilter"] == "none"

    async def test_get_single_resource(self) -> None:
        client = MagicMock()
        client.site_url = "https://example.atlassian.net"
        client.send_api_request = AsyncMock(
            return_value=_page([{"accountId": "abc", "displayName": "Ada"}], total=1)
        )
        exporter = UserExporter(client)

        result = await exporter.get_single_resource("abc")

        assert result is not None
        assert result["accountId"] == "abc"
        assert (
            client.send_api_request.await_args.kwargs["params"]["cql"] == 'user="abc"'
        )

    async def test_get_single_resource_not_found(self) -> None:
        client = MagicMock()
        client.site_url = "https://example.atlassian.net"
        client.send_api_request = AsyncMock(return_value={"results": []})
        exporter = UserExporter(client)

        assert await exporter.get_single_resource("missing") is None
