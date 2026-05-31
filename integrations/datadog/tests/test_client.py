import time
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from client import (
    DATADOG_UNKNOWN_STATUS_CODE,
    DatadogClient,
    FETCH_WINDOW_TIME_IN_SECONDS,
    MAX_PAGE_SIZE,
    _create_datadog_retry_config,
)
from integration import ObjectKind
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture
def resource_config() -> Any:
    mock_resource_config = MagicMock()
    mock_resource_config.kind = ObjectKind.SERVICE_DEPENDENCY
    mock_resource_config.selector.environment = "prod"
    mock_resource_config.selector.start_time = 2.5

    return mock_resource_config


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
        api_key="test_api_key",
        app_key="test_app_key",
        api_url="api.datadoghq.com",
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


@pytest.mark.asyncio
async def test_get_service_dependencies(
    mock_datadog_client: DatadogClient, resource_config: Any
) -> None:
    expected_return_value: dict[str, Any] = {
        "service_a": {"calls": ["service_b", "service_c"]},
        "service_b": {"calls": ["service_o"]},
        "service_c": {"calls": ["service_o"]},
        "service_o": {"calls": []},
    }

    with patch.object(
        mock_datadog_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = expected_return_value

        dependencies: list[dict[str, Any]] = []
        end_time = int(time.time())
        async for dependency_batch in mock_datadog_client.get_service_dependencies(
            env=resource_config.selector.environment,
            start_time=resource_config.selector.start_time,
        ):
            dependencies.extend(dependency_batch)
        assert len(dependencies) == 4
        items: list[dict[str, Any]] = [
            {"name": name, **details} for name, details in expected_return_value.items()
        ]
        assert dependencies == items

        parsed_start_time = int(
            time.time()
            - (FETCH_WINDOW_TIME_IN_SECONDS * resource_config.selector.start_time)
        )
        mock_request.assert_called_with(
            f"{mock_datadog_client.api_url}/api/v1/service_dependencies",
            params={
                "env": resource_config.selector.environment,
                "start": parsed_start_time,
                "end": end_time,
            },
        )


def test_datadog_retry_config_includes_transient_status_codes() -> None:
    config = _create_datadog_retry_config()

    assert HTTPStatus.INTERNAL_SERVER_ERROR in config.retry_status_codes
    assert DATADOG_UNKNOWN_STATUS_CODE in config.retry_status_codes
    assert "X-RateLimit-Reset" in config.retry_after_headers
    assert HTTPStatus.INTERNAL_SERVER_ERROR in config.ignore_retry_after_status_codes
    assert DATADOG_UNKNOWN_STATUS_CODE in config.ignore_retry_after_status_codes


@pytest.mark.asyncio
async def test_fetch_with_rate_limit_handling_retries_after_quota_wait(
    mock_datadog_client: DatadogClient,
) -> None:
    low_quota_response = httpx.Response(
        200,
        json={"series": []},
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1"},
        request=httpx.Request("GET", "https://api.datadoghq.com/api/v1/query"),
    )
    success_response = httpx.Response(
        200,
        json={"series": [{"pointlist": []}]},
        headers={"X-RateLimit-Remaining": "100"},
        request=httpx.Request("GET", "https://api.datadoghq.com/api/v1/query"),
    )

    with (
        patch.object(
            mock_datadog_client.http_client,
            "request",
            new_callable=AsyncMock,
            side_effect=[low_quota_response, success_response],
        ) as mock_request,
        patch("client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        result = await mock_datadog_client._fetch_with_rate_limit_handling(
            "https://api.datadoghq.com/api/v1/query"
        )

    assert result == {"series": [{"pointlist": []}]}
    assert mock_request.await_count == 2
    mock_sleep.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_send_api_request_logs_rate_limit_headers_on_429(
    mock_datadog_client: DatadogClient,
) -> None:
    rate_limit_response = httpx.Response(
        HTTPStatus.TOO_MANY_REQUESTS,
        request=httpx.Request("GET", "https://api.datadoghq.com/api/v1/monitor"),
        headers={
            "X-RateLimit-Remaining": "10",
            "X-RateLimit-Reset": "1710000000",
        },
    )

    with (
        patch.object(
            mock_datadog_client.http_client,
            "request",
            new_callable=AsyncMock,
            return_value=rate_limit_response,
        ),
        patch("client.logger") as mock_logger,
        pytest.raises(httpx.HTTPStatusError),
    ):
        mock_bound = MagicMock()
        mock_logger.bind.return_value = mock_bound

        await mock_datadog_client._send_api_request(
            "https://api.datadoghq.com/api/v1/monitor",
            params={"page": 556, "page_size": 100},
        )

    mock_logger.bind.assert_called_once_with(
        remaining="10",
        reset="1710000000",
        method="GET",
        url="https://api.datadoghq.com/api/v1/monitor",
    )
    mock_bound.warning.assert_called_once()
