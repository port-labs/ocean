import pytest
from typing import Any
from unittest.mock import AsyncMock, patch, MagicMock

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from client import DatadogClient, MAX_PAGE_SIZE


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "api_key": "test_api_key",
            "app_key": "test_app_key",
            "api_url": "api.datadoghq.com",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_datadog_client() -> DatadogClient:
    return DatadogClient(
        api_key="test_api_key", app_key="test_app_key", api_url="api.datadoghq.com"
    )


@pytest.mark.asyncio
async def test_get_teams(mock_datadog_client: DatadogClient) -> None:
    teams_response: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "team"}, {"id": "2", "type": "team"}]
    }
    empty_response: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [teams_response, empty_response]

        teams = []
        async for team_batch in mock_datadog_client.get_teams():
            teams.extend(team_batch)

        assert len(teams) == 2
        assert teams == teams_response["data"]
        mock_request.assert_called_with(
            f"{mock_datadog_client.api_url}/api/v2/team",
            params={"page[size]": MAX_PAGE_SIZE, "page[number]": 1},
        )


@pytest.mark.asyncio
async def test_get_teams_multiple_pages(mock_datadog_client: DatadogClient) -> None:
    first_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "team"}]
    }
    second_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "2", "type": "team"}]
    }
    third_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "3", "type": "team"}]
    }
    empty_page: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [first_page, second_page, third_page, empty_page]

        teams = []
        async for team_batch in mock_datadog_client.get_teams():
            teams.extend(team_batch)

        assert len(teams) == 3
        assert teams == first_page["data"] + second_page["data"] + third_page["data"]
        assert mock_request.call_count == 4


@pytest.mark.asyncio
async def test_get_users(mock_datadog_client: DatadogClient) -> None:
    users_response: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "users"}, {"id": "2", "type": "users"}]
    }
    empty_response: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [users_response, empty_response]

        users = []
        async for user_batch in mock_datadog_client.get_users():
            users.extend(user_batch)

        assert len(users) == 2
        assert users == users_response["data"]
        mock_request.assert_called_with(
            f"{mock_datadog_client.api_url}/api/v2/users",
            params={"page[size]": MAX_PAGE_SIZE, "page[number]": 1},
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
        mock_datadog_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [first_page, second_page, third_page, empty_page]

        users = []
        async for user_batch in mock_datadog_client.get_users():
            users.extend(user_batch)

        assert len(users) == 3
        assert users == first_page["data"] + second_page["data"] + third_page["data"]
        assert mock_request.call_count == 4


@pytest.mark.asyncio
async def test_get_team_members(mock_datadog_client: DatadogClient) -> None:
    members_response: dict[str, list[dict[str, Any]]] = {
        "included": [{"id": "1", "type": "users"}, {"id": "2", "type": "users"}]
    }
    empty_response: dict[str, list[dict[str, Any]]] = {"included": []}

    with patch.object(
        mock_datadog_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [members_response, empty_response]

        members = []
        async for member_batch in mock_datadog_client.get_team_members("team1"):
            members.extend(member_batch)

        assert len(members) == 2
        assert members == members_response["included"]
        mock_request.assert_called_with(
            f"{mock_datadog_client.api_url}/api/v2/team/team1/memberships",
            params={"page[size]": MAX_PAGE_SIZE, "page[number]": 1},
        )


@pytest.mark.asyncio
async def test_get_team_members_multiple_pages(
    mock_datadog_client: DatadogClient,
) -> None:
    first_page: dict[str, list[dict[str, Any]]] = {
        "included": [{"id": "1", "type": "users"}]
    }
    second_page: dict[str, list[dict[str, Any]]] = {
        "included": [{"id": "2", "type": "users"}]
    }
    third_page: dict[str, list[dict[str, Any]]] = {
        "included": [{"id": "3", "type": "users"}]
    }
    empty_page: dict[str, list[dict[str, Any]]] = {"included": []}

    with patch.object(
        mock_datadog_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [first_page, second_page, third_page, empty_page]

        members = []
        async for member_batch in mock_datadog_client.get_team_members("team1"):
            members.extend(member_batch)

        assert len(members) == 3
        assert (
            members
            == first_page["included"] + second_page["included"] + third_page["included"]
        )
        assert mock_request.call_count == 4


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists(
    mock_datadog_client: DatadogClient,
) -> None:
    with (
        patch.object(
            mock_datadog_client, "_webhook_exists", new_callable=AsyncMock
        ) as mock_exists,
        patch.object(
            mock_datadog_client, "_send_api_request", new_callable=AsyncMock
        ) as mock_send,
    ):
        mock_exists.return_value = False
        mock_send.return_value = {"status": "created"}
        base_url = "https://example.com"
        webhook_secret = "test_secret"
        await mock_datadog_client.create_webhooks_if_not_exists(
            base_url, webhook_secret
        )
        expected_url = f"https://port:{webhook_secret}@example.com/integration/webhook"
        mock_send.assert_awaited_once()
        call_args = mock_send.call_args[1]
        assert call_args["json_data"]["url"] == expected_url


@pytest.mark.asyncio
async def test_create_webhooks_if_exists(mock_datadog_client: DatadogClient) -> None:
    with (
        patch.object(
            mock_datadog_client, "_webhook_exists", new_callable=AsyncMock
        ) as mock_exists,
        patch.object(
            mock_datadog_client, "_send_api_request", new_callable=AsyncMock
        ) as mock_send,
    ):
        mock_exists.return_value = True
        await mock_datadog_client.create_webhooks_if_not_exists(
            "https://example.com", "test_secret"
        )
        mock_send.assert_not_called()
