import pytest
from typing import Any, Optional
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from clients.pagerduty import PagerDutyClient


TEST_INTEGRATION_CONFIG: dict[str, str] = {
    "token": "mock-token",
    "api_url": "https://api.pagerduty.com",
    "app_host": "https://app.example.com",
}

TEST_DATA: dict[str, list[dict[str, Any]]] = {
    "users": [
        {"id": "PU123", "email": "user1@example.com"},
        {"id": "PU456", "email": "user2@example.com"},
    ],
    "services": [
        {"id": "PS123", "name": "Service 1", "escalation_policy": {"id": "PE123"}},
        {"id": "PS456", "name": "Service 2", "escalation_policy": {"id": "PE456"}},
    ],
    "oncalls": [
        {
            "escalation_policy": {"id": "PE123"},
            "user": {"id": "PU123", "name": "User 1"},
        },
        {
            "escalation_policy": {"id": "PE456"},
            "user": {"id": "PU456", "name": "User 2"},
        },
    ],
    "schedules": [{"users": [{"id": "PU123"}, {"id": "PU456"}]}],
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "token": TEST_INTEGRATION_CONFIG["token"],
            "api_url": TEST_INTEGRATION_CONFIG["api_url"],
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = TEST_INTEGRATION_CONFIG["app_host"]
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None

        def get_mock_external_access_token() -> str:
            return "pd_test_external_access_token"

        mock_ocean_app.load_external_oauth_access_token = get_mock_external_access_token
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def client() -> PagerDutyClient:
    """Create a PagerDuty client fixture."""
    return PagerDutyClient(**TEST_INTEGRATION_CONFIG)


@pytest.mark.asyncio
class TestPagerDutyClient:
    async def test_paginate_request_to_pager_duty(
        self, client: PagerDutyClient
    ) -> None:
        # Simulate multiple pages of data
        mock_responses = [
            MagicMock(
                json=lambda: {
                    "users": TEST_DATA["users"][:1],
                    "more": True,
                    "limit": 1,
                    "offset": 0,
                }
            ),
            MagicMock(json=lambda: {"users": TEST_DATA["users"][1:], "more": False}),
        ]

        with patch(
            "port_ocean.utils.http_async_client.request", side_effect=mock_responses
        ):
            collected_data: list[dict[str, Any]] = []
            async for page in client.paginate_request_to_pager_duty("users"):
                collected_data.extend(page)

            assert collected_data == TEST_DATA["users"]

    async def test_get_single_resource(self, client: PagerDutyClient) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"user": TEST_DATA["users"][0]}

        with patch(
            "port_ocean.utils.http_async_client.request", return_value=mock_response
        ):
            result = await client.get_single_resource("users", "PU123")
            assert result == {"user": TEST_DATA["users"][0]}

    async def test_create_webhooks_if_not_exists(self, client: PagerDutyClient) -> None:
        # Scenario 1: No existing webhooks
        no_webhook_response = MagicMock()
        no_webhook_response.json.return_value = {
            "webhook_subscriptions": [],
            "more": False,
        }

        create_webhook_response = MagicMock()
        create_webhook_response.json.return_value = {
            "webhook_subscription": {"id": "new-webhook"}
        }

        with patch(
            "port_ocean.utils.http_async_client.request",
            side_effect=[no_webhook_response, create_webhook_response],
        ):
            await client.create_webhooks_if_not_exists()

        # Scenario 2: Webhook already exists
        existing_webhook_response = MagicMock()
        existing_webhook_response.json.return_value = {
            "webhook_subscriptions": [
                {
                    "delivery_method": {
                        "type": "http_delivery_method",
                        "url": f"{TEST_INTEGRATION_CONFIG['app_host']}/integration/webhook",
                    }
                }
            ],
            "more": False,
        }

        with patch(
            "port_ocean.utils.http_async_client.request",
            return_value=existing_webhook_response,
        ):
            await client.create_webhooks_if_not_exists()

        # Scenario 3: No app host
        client_no_host = PagerDutyClient(
            token=TEST_INTEGRATION_CONFIG["token"],
            api_url=TEST_INTEGRATION_CONFIG["api_url"],
            app_host=None,
        )
        await client_no_host.create_webhooks_if_not_exists()

    async def test_get_oncall_user(self, client: PagerDutyClient) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "oncalls": TEST_DATA["oncalls"],
            "more": False,
        }

        with patch(
            "port_ocean.utils.http_async_client.request", return_value=mock_response
        ):
            result = await client.get_oncall_user("PE123", "PE456")
            assert result == TEST_DATA["oncalls"]

    async def test_update_oncall_users(self, client: PagerDutyClient) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "oncalls": TEST_DATA["oncalls"],
            "more": False,
        }

        with patch(
            "port_ocean.utils.http_async_client.request", return_value=mock_response
        ):
            services: list[dict[str, Any]] = TEST_DATA["services"].copy()
            updated = await client.update_oncall_users(services)

            assert len(updated) == len(services)
            for service in updated:
                assert "__oncall_user" in service
                matching_oncalls = [
                    oncall
                    for oncall in TEST_DATA["oncalls"]
                    if oncall["escalation_policy"]["id"]
                    == service["escalation_policy"]["id"]
                ]
                assert service["__oncall_user"] == matching_oncalls

    async def test_get_incident_analytics(self, client: PagerDutyClient) -> None:
        mock_response = MagicMock()
        expected_analytics: dict[str, int] = {
            "total_incidents": 10,
            "mean_time_to_resolve": 3600,
        }
        mock_response.json.return_value = expected_analytics

        with patch(
            "port_ocean.utils.http_async_client.request", return_value=mock_response
        ):
            result = await client.get_incident_analytics("INCIDENT123")
            assert result == expected_analytics

    async def test_get_service_analytics(self, client: PagerDutyClient) -> None:
        # Scenario 1: Successful data retrieval
        mock_response = MagicMock()
        analytics_response = [
            {"service_id": "SERVICE123", "mean_incidents": 2, "total_incidents": 5},
            {"service_id": "SERVICE456", "mean_incidents": 3, "total_incidents": 7},
        ]
        mock_response.json.return_value = {"data": analytics_response}

        with patch(
            "port_ocean.utils.http_async_client.request", return_value=mock_response
        ):
            result = await client.get_service_analytics(["SERVICE123", "SERVICE456"])
            assert result == analytics_response

    async def test_send_api_request(self, client: PagerDutyClient) -> None:
        # Successful request
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.raise_for_status.return_value = None

        with patch(
            "port_ocean.utils.http_async_client.request", return_value=mock_response
        ):
            result = await client.send_api_request("test/endpoint")
            assert result == {"result": "success"}

        # 404 request
        not_found_response = MagicMock()
        not_found_response.status_code = 404
        not_found_response.json.return_value = {}
        not_found_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=not_found_response
        )

        with patch(
            "port_ocean.utils.http_async_client.request",
            return_value=not_found_response,
        ):
            result = await client.send_api_request("nonexistent/endpoint")
            assert result == {}

    async def test_transform_user_ids_to_emails(self, client: PagerDutyClient) -> None:
        # Mock the fetch_and_cache_users method to populate user cache
        async def mock_fetch_and_cache_users() -> None:
            pass

        # Mock get_cached_user to return emails
        def mock_get_cached_user(user_id: str) -> Optional[str]:
            user_map = {"PU123": "user1@example.com", "PU456": "user2@example.com"}
            return user_map.get(user_id)

        with patch.object(
            client, "fetch_and_cache_users", side_effect=mock_fetch_and_cache_users
        ):
            with patch.object(
                client, "get_cached_user", side_effect=mock_get_cached_user
            ):
                schedules: list[dict[str, Any]] = TEST_DATA["schedules"].copy()
                transformed = await client.transform_user_ids_to_emails(schedules)

                assert len(transformed[0]["users"]) == 2
                assert transformed[0]["users"][0]["__email"] == "user1@example.com"
                assert transformed[0]["users"][1]["__email"] == "user2@example.com"

    def test_from_ocean_configuration(self) -> None:
        client = PagerDutyClient.from_ocean_configuration()

        assert client.token == TEST_INTEGRATION_CONFIG["token"]
        assert client.api_url == TEST_INTEGRATION_CONFIG["api_url"]
        assert client.app_host == TEST_INTEGRATION_CONFIG["app_host"]

    def test_get_auth_header(self, client: PagerDutyClient) -> None:
        # Test OAuth token
        oauth_token = "pd_test_token"
        assert client._get_auth_header(oauth_token) == "Bearer pd_test_token"

        # Test regular token
        regular_token = "test_token"
        assert client._get_auth_header(regular_token) == "Token token=test_token"

    def test_refresh_request_auth_creds(self, client: PagerDutyClient) -> None:
        # Create a mock request with headers
        request = httpx.Request("GET", "https://api.pagerduty.com/test")
        request.headers = httpx.Headers()
        refreshed_request = client.refresh_request_auth_creds(request)
        assert (
            refreshed_request.headers["Authorization"]
            == "Bearer pd_test_external_access_token"
        )

    def test_headers_property(self) -> None:
        # Test with OAuth token
        oauth_client = PagerDutyClient(
            token="pd_test_token",
            api_url=TEST_INTEGRATION_CONFIG["api_url"],
            app_host=TEST_INTEGRATION_CONFIG["app_host"],
        )
        oauth_headers = oauth_client.headers
        assert oauth_headers["Content-Type"] == "application/json"
        assert oauth_headers["Authorization"] == "Bearer pd_test_token"
        assert oauth_headers["Accept"] == "application/vnd.pagerduty+json;version=2"

        # Test with regular token
        regular_client = PagerDutyClient(
            token="test_token",
            api_url=TEST_INTEGRATION_CONFIG["api_url"],
            app_host=TEST_INTEGRATION_CONFIG["app_host"],
        )
        regular_headers = regular_client.headers
        assert regular_headers["Content-Type"] == "application/json"
        assert regular_headers["Authorization"] == "Token token=test_token"
        assert "Accept" not in regular_headers

    async def test_refresh_request_auth_creds_fallback_to_token(
        self, client: PagerDutyClient
    ) -> None:
        # Setup
        request = httpx.Request("GET", "https://api.pagerduty.com")
        request.headers = httpx.Headers()

        # Execute
        with patch(
            "port_ocean.context.ocean.ocean.app.load_external_oauth_access_token",
            return_value=None,
        ):
            result = client.refresh_request_auth_creds(request)

        # Assert
        assert result.headers["Authorization"] == "Token token=mock-token"
