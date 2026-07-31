from typing import Any
from unittest.mock import AsyncMock
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.ses.configuration_set.actions import (
    ConfigurationSetRecord,
    GetConfigurationSetAction,
    ListConfigurationSetsAction,
    SesConfigurationSetActionsMap,
)
from aws.core.interfaces.action import Action


class TestGetConfigurationSetAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock SESv2 client for testing."""
        mock_client = AsyncMock()
        mock_client.get_configuration_set = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetConfigurationSetAction:
        """Create a GetConfigurationSetAction instance for testing."""
        return GetConfigurationSetAction(mock_client)

    def test_inheritance(self, action: GetConfigurationSetAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetConfigurationSetAction) -> None:
        """Test that the raw get_configuration_set response is returned unchanged, minus ResponseMetadata."""
        configuration_set_fields = {
            "ConfigurationSetName": "my-config-set",
            "TrackingOptions": {"CustomRedirectDomain": "tracking.example.com"},
            "DeliveryOptions": {"TlsPolicy": "REQUIRE", "SendingPoolName": "my-pool"},
            "ReputationOptions": {
                "ReputationMetricsEnabled": True,
                "LastFreshStart": "2024-01-15T10:30:00Z",
            },
            "SendingOptions": {"SendingEnabled": True},
            "SuppressionOptions": {"SuppressedReasons": ["BOUNCE", "COMPLAINT"]},
            "Tags": [{"Key": "Environment", "Value": "production"}],
        }
        action.client.get_configuration_set.return_value = {
            "ResponseMetadata": {
                "RequestId": "abc123",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {"content-type": "application/x-amz-json-1.1"},
                "RetryAttempts": 0,
            },
            **configuration_set_fields,
        }

        test_configuration_sets: list[ConfigurationSetRecord] = [
            {"ConfigurationSetName": "my-config-set"}
        ]
        result = await action._execute(test_configuration_sets)

        assert len(result) == 1
        assert result[0] == configuration_set_fields
        assert "ResponseMetadata" not in result[0]

        action.client.get_configuration_set.assert_called_once_with(
            ConfigurationSetName="my-config-set"
        )

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: GetConfigurationSetAction) -> None:
        """Test execution with empty configuration sets list."""
        result = await action._execute([])

        assert result == []
        action.client.get_configuration_set.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: GetConfigurationSetAction
    ) -> None:
        """Test execution with recoverable exception preserves an empty placeholder."""
        error = ClientError(
            error_response={"Error": {"Code": "NotFoundException"}},
            operation_name="GetConfigurationSet",
        )
        action.client.get_configuration_set.side_effect = error

        test_configuration_sets: list[ConfigurationSetRecord] = [
            {"ConfigurationSetName": "my-config-set"}
        ]
        result = await action._execute(test_configuration_sets)

        assert result == [{}]
        action.client.get_configuration_set.assert_called_once_with(
            ConfigurationSetName="my-config-set"
        )

    @pytest.mark.asyncio
    async def test_execute_preserves_index_alignment_with_middle_failure(
        self, action: GetConfigurationSetAction
    ) -> None:
        """Middle configuration set fails recoverably; results keep aligned positions."""

        def mock_get_configuration_set(
            ConfigurationSetName: str, **kwargs: Any
        ) -> dict[str, Any]:
            if ConfigurationSetName == "fail-set":
                raise ClientError(
                    error_response={"Error": {"Code": "AccessDenied"}},
                    operation_name="GetConfigurationSet",
                )
            return {
                "ConfigurationSetName": ConfigurationSetName,
                "SendingOptions": {"SendingEnabled": True},
                "ReputationOptions": {"ReputationMetricsEnabled": True},
            }

        action.client.get_configuration_set.side_effect = mock_get_configuration_set

        configuration_sets: list[ConfigurationSetRecord] = [
            {"ConfigurationSetName": "first-set"},
            {"ConfigurationSetName": "fail-set"},
            {"ConfigurationSetName": "third-set"},
        ]

        result = await action._execute(configuration_sets)

        assert len(result) == 3
        assert result[0]["ConfigurationSetName"] == "first-set"
        assert result[1] == {}
        assert result[2]["ConfigurationSetName"] == "third-set"

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: GetConfigurationSetAction
    ) -> None:
        """Test execution with non-recoverable exception."""
        error = ClientError(
            error_response={"Error": {"Code": "InternalServerError"}},
            operation_name="GetConfigurationSet",
        )
        action.client.get_configuration_set.side_effect = error

        test_configuration_sets: list[ConfigurationSetRecord] = [
            {"ConfigurationSetName": "my-config-set"}
        ]

        with pytest.raises(ClientError):
            await action._execute(test_configuration_sets)


class TestListConfigurationSetsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock SESv2 client for testing."""
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListConfigurationSetsAction:
        """Create a ListConfigurationSetsAction instance for testing."""
        return ListConfigurationSetsAction(mock_client)

    def test_inheritance(self, action: ListConfigurationSetsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: ListConfigurationSetsAction) -> None:
        """Test that raw list_configuration_sets items are returned unchanged."""
        test_configuration_sets: list[ConfigurationSetRecord] = [
            {"ConfigurationSetName": "my-config-set"},
            {"ConfigurationSetName": "another-config-set"},
        ]

        result = await action._execute(test_configuration_sets)

        assert result == test_configuration_sets

    @pytest.mark.asyncio
    async def test_execute_empty_list(
        self, action: ListConfigurationSetsAction
    ) -> None:
        """Test execution with empty configuration sets list."""
        result = await action._execute([])
        assert result == []


class TestSesConfigurationSetActionsMap:

    def test_defaults_include_required_actions(self) -> None:
        """Test that the defaults list contains the required actions."""
        actions_map = SesConfigurationSetActionsMap()
        assert ListConfigurationSetsAction in actions_map.defaults
        assert GetConfigurationSetAction in actions_map.defaults

    def test_no_options(self) -> None:
        """Test that there are no optional actions."""
        actions_map = SesConfigurationSetActionsMap()
        assert actions_map.options == []
