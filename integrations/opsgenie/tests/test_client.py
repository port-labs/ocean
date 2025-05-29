import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.context.event import event_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from client import OpsGenieClient, ObjectKind, PAGE_SIZE  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "api_url": "https://api.opsgenie.com",
            "token": "test-token",
        }
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.asyncio
class TestOpsGenieClient:
    @pytest.fixture
    def client(self) -> OpsGenieClient:
        return OpsGenieClient(token="test-token", api_url="https://api.opsgenie.com")

    async def test_api_auth_header(self, client: OpsGenieClient) -> None:
        # Arrange
        expected_header = {"Authorization": "GenieKey test-token"}

        # Act
        result = client.api_auth_header

        # Assert
        assert result == expected_header

    async def test_get_resource_api_version(self, client: OpsGenieClient) -> None:
        # Arrange
        resource_type = ObjectKind.ALERT
        expected_version = "v2"

        # Act
        result = await client.get_resource_api_version(resource_type)

        # Assert
        assert result == expected_version

    async def test_get_single_resource_success(self, client: OpsGenieClient) -> None:
        # Arrange
        url = "https://api.opsgenie.com/v2/alerts/123"
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"id": "123", "name": "Test Alert"}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            client.http_client, "get", AsyncMock(return_value=mock_response)
        ) as mock_get:
            # Act
            async with event_context("test_event"):
                result = await client._get_single_resource(url)

            # Assert
            assert result == {"data": {"id": "123", "name": "Test Alert"}}
            mock_get.assert_called_once_with(url=url, params=None)
            mock_response.raise_for_status.assert_called_once()

    async def test_get_single_resource_http_status_error(
        self, client: OpsGenieClient
    ) -> None:
        # Arrange
        url = "https://api.opsgenie.com/v2/alerts/123"
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )

        with patch.object(
            client.http_client, "get", AsyncMock(return_value=mock_response)
        ):
            # Act & Assert
            async with event_context("test_event"):
                with pytest.raises(httpx.HTTPStatusError):
                    await client._get_single_resource(url)

    async def test_get_paginated_resources_success(
        self, client: OpsGenieClient
    ) -> None:
        """Test get_paginated_resources with successful pagination"""
        # Arrange
        resource_type = ObjectKind.ALERT
        base_url = f"{client.api_url}/v2/alerts"
        mock_responses = [
            {
                "data": [{"id": "1"}, {"id": "2"}],
                "paging": {"next": f"{base_url}?offset=2&limit={PAGE_SIZE}"},
            },
            {"data": [{"id": "3"}], "paging": {}},
        ]

        with patch.object(
            client, "_get_single_resource", AsyncMock(side_effect=mock_responses)
        ):
            # Act
            async with event_context("test_event"):
                results = []
                async for page in client.get_paginated_resources(resource_type):
                    results.extend(page)

            # Assert
            assert results == [{"id": "1"}, {"id": "2"}, {"id": "3"}]

    async def test_get_alert_success(self, client: OpsGenieClient) -> None:
        # Arrange
        identifier = "123"
        mock_response = {"data": {"id": "123", "name": "Test Alert"}}

        with patch.object(
            client, "_get_single_resource", AsyncMock(return_value=mock_response)
        ) as mock_get:
            # Act
            async with event_context("test_event"):
                result = await client.get_alert(identifier)

            # Assert
            assert result == {"id": "123", "name": "Test Alert"}
            mock_get.assert_called_once_with(f"{client.api_url}/v2/alerts/{identifier}")

    async def test_get_oncall_users_success(self, client: OpsGenieClient) -> None:
        # Arrange
        schedule_identifier = "sched123"
        mock_response = {"data": [{"user": "user1"}, {"user": "user2"}]}

        with patch.object(
            client, "_get_single_resource", AsyncMock(return_value=mock_response)
        ) as mock_get:
            # Act
            async with event_context("test_event"):
                result = await client.get_oncall_users(schedule_identifier)

            # Assert
            assert result == [{"user": "user1"}, {"user": "user2"}]
            mock_get.assert_called_once_with(
                f"{client.api_url}/v2/schedules/{schedule_identifier}/on-calls?flat=true"
            )

    async def test_get_team_members_success(self, client: OpsGenieClient) -> None:
        # Arrange
        team_identifier = "team123"
        mock_response = {"data": {"members": [{"id": "user1"}, {"id": "user2"}]}}

        with patch.object(
            client, "_get_single_resource", AsyncMock(return_value=mock_response)
        ) as mock_get:
            # Act
            async with event_context("test_event"):
                result = await client.get_team_members(team_identifier)

            # Assert
            assert result == [{"id": "user1"}, {"id": "user2"}]
            mock_get.assert_called_once_with(
                f"{client.api_url}/v2/teams/{team_identifier}"
            )

    async def test_get_paginated_resources_respects_max_offset_limit(
        self, client: OpsGenieClient
    ) -> None:
        """Test get_paginated_resources stops at MAX_OPSGENIE_OFFSET_LIMIT for alerts, incidents, and services."""
        # Arrange
        resource_types = [ObjectKind.ALERT, ObjectKind.INCIDENT, ObjectKind.SERVICE]
        base_urls = {
            ObjectKind.ALERT: f"{client.api_url}/v2/alerts",
            ObjectKind.INCIDENT: f"{client.api_url}/v2/incidents",
            ObjectKind.SERVICE: f"{client.api_url}/v2/services",
        }

        for resource_type in resource_types:
            base_url = base_urls[resource_type]
            max_offset_limit = client.get_resource_offset_limit(resource_type)
            if max_offset_limit is None:
                pytest.skip(f"No offset limit defined for {resource_type.value}")

            mock_responses = []
            current_offset = max_offset_limit - PAGE_SIZE
            mock_responses.append(
                {
                    "data": [
                        {"id": f"{current_offset}_1"},
                        {"id": f"{current_offset}_2"},
                    ],
                    "paging": {
                        "next": f"{base_url}?offset={current_offset + PAGE_SIZE}&limit={PAGE_SIZE}"
                    },
                }
            )
            # Response at or beyond max_offset_limit should not be fetched
            mock_responses.append(
                {
                    "data": [{"id": f"{current_offset + PAGE_SIZE}_1"}],
                    "paging": {},
                }
            )

            with patch.object(
                client, "_get_single_resource", AsyncMock(side_effect=mock_responses)
            ) as mock_get:
                # Act
                async with event_context("test_event"):
                    results = []
                    async for page in client.get_paginated_resources(resource_type):
                        results.extend(page)

                # Assert
                expected_results = [
                    {"id": f"{current_offset}_1"},
                    {"id": f"{current_offset}_2"},
                    {"id": f"{current_offset + PAGE_SIZE}_1"},
                ]

                assert results == expected_results
                assert mock_get.call_count == 2
