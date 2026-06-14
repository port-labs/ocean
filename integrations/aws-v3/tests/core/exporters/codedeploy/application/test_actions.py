from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.codedeploy.application.actions import (
    GetCodeDeployApplicationDetailsAction,
    GetCodeDeployApplicationTagsAction,
    CodeDeployApplicationActionInput,
)
from aws.core.interfaces.action import Action


class TestGetCodeDeployApplicationDetailsAction:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        mock_client.batch_get_applications = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetCodeDeployApplicationDetailsAction:
        """Create a GetCodeDeployApplicationDetailsAction instance for testing."""
        return GetCodeDeployApplicationDetailsAction(mock_client)

    @pytest.mark.asyncio
    async def test_execute_success(
        self, action: GetCodeDeployApplicationDetailsAction
    ) -> None:
        # Arrange
        resources: CodeDeployApplicationActionInput = {
            "applications": ["a", "b"],
            "extras": {"region": "region", "account_id": "account_id"},
        }
        mock_response_one = {"applicationName": "b"}
        mock_response_two = {"applicationName": "a"}
        action.client.batch_get_applications.return_value = {
            "applicationsInfo": [mock_response_one, mock_response_two]
        }

        # Act
        result = await action._execute(resources)

        # Assert
        assert result == [mock_response_two, mock_response_one]
        action.client.batch_get_applications.assert_called_once_with(
            applicationNames=resources["applications"]
        )

    @pytest.mark.asyncio
    async def test_execute_empty_applications_info(
        self, action: GetCodeDeployApplicationDetailsAction
    ) -> None:
        # Arrange
        resources: CodeDeployApplicationActionInput = {
            "applications": ["a", "b"],
            "extras": {"region": "region", "account_id": "account_id"},
        }
        action.client.batch_get_applications.return_value = {}

        # Act
        result = await action._execute(resources)

        # Assert
        assert result == []
        action.client.batch_get_applications.assert_called_once_with(
            applicationNames=resources['applications']
        )


class TestGetCodeDeployApplicationTagsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        mock_client.list_tags_for_resource = AsyncMock()
        # Expose botocore's ClientError on the mocked client so the action's
        # `except self.client.exceptions.ClientError` clause catches our raises.
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ClientError = ClientError
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetCodeDeployApplicationTagsAction:
        """Create a GetCodeDeployApplicationTagsAction instance for testing."""
        return GetCodeDeployApplicationTagsAction(mock_client)

    def test_inheritance(self, action: GetCodeDeployApplicationTagsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(
        self, action: GetCodeDeployApplicationTagsAction
    ) -> None:
        """Test successful execution of list_tags_for_resource."""
        resources = [
            {
                "applicationName": "app-1",
                "region": "us-east-1",
                "accountId": "123456789012",
            },
            {
                "applicationName": "app-2",
                "region": "us-east-1",
                "accountId": "123456789012",
            },
        ]

        def mock_list_tags(ResourceArn: str, **kwargs: Any) -> dict[str, Any]:
            if ResourceArn.endswith(":application:app-1"):
                return {"Tags": [{"Key": "Environment", "Value": "production"}]}
            elif ResourceArn.endswith(":application:app-2"):
                return {"Tags": [{"Key": "Environment", "Value": "staging"}]}
            return {"Tags": []}

        action.client.list_tags_for_resource.side_effect = mock_list_tags

        result = await action.execute(resources)

        assert result == [
            {"Tags": [{"Key": "Environment", "Value": "production"}]},
            {"Tags": [{"Key": "Environment", "Value": "staging"}]},
        ]

        assert action.client.list_tags_for_resource.call_count == 2
        action.client.list_tags_for_resource.assert_any_call(
            ResourceArn="arn:aws:codedeploy:us-east-1:123456789012:application:app-1"
        )
        action.client.list_tags_for_resource.assert_any_call(
            ResourceArn="arn:aws:codedeploy:us-east-1:123456789012:application:app-2"
        )

    @pytest.mark.asyncio
    async def test_execute_empty_resources(
        self, action: GetCodeDeployApplicationTagsAction
    ) -> None:
        """Test execution with empty resources list."""
        result = await action.execute([])

        assert result == []
        action.client.list_tags_for_resource.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codedeploy.application.actions.logger")
    async def test_execute_missing_resource_returns_empty_tags(
        self,
        mock_logger: MagicMock,
        action: GetCodeDeployApplicationTagsAction,
    ) -> None:
        """ResourceNotFoundException is swallowed and yields an empty Tags list."""
        resources = [
            {
                "applicationName": "missing-app",
                "region": "us-east-1",
                "accountId": "123456789012",
            }
        ]
        action.client.list_tags_for_resource.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Not found",
                }
            },
            "ListTagsForResource",
        )

        result = await action.execute(resources)

        assert result == [{"Tags": []}]
        mock_logger.info.assert_called_once_with(
            "No tags found for CodeDeploy application missing-app"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codedeploy.application.actions.logger")
    async def test_execute_invalid_parameter_returns_empty_tags(
        self,
        mock_logger: MagicMock,
        action: GetCodeDeployApplicationTagsAction,
    ) -> None:
        """InvalidParameterException is also treated as no-tags."""
        resources = [
            {
                "applicationName": "bad-app",
                "region": "us-east-1",
                "accountId": "123456789012",
            }
        ]
        action.client.list_tags_for_resource.side_effect = ClientError(
            {
                "Error": {
                    "Code": "InvalidParameterException",
                    "Message": "Invalid",
                }
            },
            "ListTagsForResource",
        )

        result = await action.execute(resources)

        assert result == [{"Tags": []}]
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codedeploy.application.actions.logger")
    async def test_execute_unhandled_client_error_is_logged_and_skipped(
        self,
        mock_logger: MagicMock,
        action: GetCodeDeployApplicationTagsAction,
    ) -> None:
        """Unhandled ClientError codes are re-raised inside the worker; asyncio.gather
        captures them and the action logs an error and skips the resource."""
        resources = [
            {
                "applicationName": "app-ok",
                "region": "us-east-1",
                "accountId": "123456789012",
            },
            {
                "applicationName": "app-fail",
                "region": "us-east-1",
                "accountId": "123456789012",
            },
        ]

        def mock_list_tags(ResourceArn: str, **kwargs: Any) -> dict[str, Any]:
            if ResourceArn.endswith(":application:app-ok"):
                return {"Tags": [{"Key": "Owner", "Value": "team"}]}
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                "ListTagsForResource",
            )

        action.client.list_tags_for_resource.side_effect = mock_list_tags

        result = await action.execute(resources)

        # Only the successful resource is returned
        assert result == [{"Tags": [{"Key": "Owner", "Value": "team"}]}]

        # The failure was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Error fetching tags for CodeDeploy application 'app-fail'" in error_call
        assert "Access denied" in error_call

    @pytest.mark.asyncio
    async def test_execute_empty_tag_list(
        self, action: GetCodeDeployApplicationTagsAction
    ) -> None:
        """Test execution when application has no tags."""
        resources = [
            {
                "applicationName": "app-1",
                "region": "us-east-1",
                "accountId": "123456789012",
            }
        ]
        action.client.list_tags_for_resource.return_value = {"Tags": []}

        result = await action.execute(resources)

        assert result == [{"Tags": []}]
        action.client.list_tags_for_resource.assert_called_once_with(
            ResourceArn="arn:aws:codedeploy:us-east-1:123456789012:application:app-1"
        )
