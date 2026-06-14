from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.codedeploy.application.actions import (
    GetCodeDeployApplicationDetailsAction,
    GetCodeDeployApplicationTagsAction,
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

    def test_inheritance(self, action: GetCodeDeployApplicationDetailsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(
        self, action: GetCodeDeployApplicationDetailsAction
    ) -> None:
        """Test successful execution of batch_get_applications."""
        resources = [
            {"applicationName": "app-b"},
            {"applicationName": "app-a"},
        ]
        create_time = datetime(2023, 12, 1, 10, 30)
        action.client.batch_get_applications.return_value = {
            "applicationsInfo": [
                {
                    "applicationName": "app-b",
                    "applicationId": "id-b",
                    "createTime": create_time,
                    "linkedToGitHub": False,
                    "gitHubAccountName": "",
                    "computePlatform": "Server",
                },
                {
                    "applicationName": "app-a",
                    "applicationId": "id-a",
                    "createTime": create_time,
                    "linkedToGitHub": True,
                    "gitHubAccountName": "octo",
                    "computePlatform": "Lambda",
                },
            ]
        }

        result = await action.execute(resources)

        assert len(result) == 2
        # Results are sorted by ApplicationName
        assert result[0]["ApplicationName"] == "app-a"
        assert result[0]["ApplicationId"] == "id-a"
        assert result[0]["ComputePlatform"] == "Lambda"
        assert result[0]["LinkedToGitHub"] is True
        assert result[0]["GitHubAccountName"] == "octo"
        assert result[0]["CreateTime"] == create_time
        assert result[1]["ApplicationName"] == "app-b"
        assert result[1]["ApplicationId"] == "id-b"

        action.client.batch_get_applications.assert_called_once_with(
            applicationNames=["app-b", "app-a"]
        )

    @pytest.mark.asyncio
    async def test_execute_empty_resources(
        self, action: GetCodeDeployApplicationDetailsAction
    ) -> None:
        """Test execution with empty resources list."""
        result = await action.execute([])

        assert result == []
        action.client.batch_get_applications.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_empty_applications_info(
        self, action: GetCodeDeployApplicationDetailsAction
    ) -> None:
        """Test execution when API returns no applicationsInfo."""
        resources = [{"applicationName": "missing"}]
        action.client.batch_get_applications.return_value = {"applicationsInfo": []}

        result = await action.execute(resources)

        assert result == []
        action.client.batch_get_applications.assert_called_once_with(
            applicationNames=["missing"]
        )

    @pytest.mark.asyncio
    async def test_execute_missing_fields_use_defaults(
        self, action: GetCodeDeployApplicationDetailsAction
    ) -> None:
        """Test that missing optional fields fall back to defaults."""
        resources = [{"applicationName": "app-1"}]
        action.client.batch_get_applications.return_value = {
            "applicationsInfo": [{"applicationName": "app-1"}]
        }

        result = await action.execute(resources)

        assert result == [
            {
                "ApplicationName": "app-1",
                "ApplicationId": "",
                "CreateTime": None,
                "LinkedToGitHub": None,
                "GitHubAccountName": None,
                "ComputePlatform": None,
            }
        ]

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codedeploy.application.actions.logger")
    async def test_execute_logs_success(
        self,
        mock_logger: MagicMock,
        action: GetCodeDeployApplicationDetailsAction,
    ) -> None:
        """Test that a success log message is emitted with the right count."""
        resources = [{"applicationName": "app-1"}]
        action.client.batch_get_applications.return_value = {
            "applicationsInfo": [{"applicationName": "app-1", "applicationId": "id-1"}]
        }

        await action.execute(resources)

        mock_logger.info.assert_called_once_with(
            "Successfully fetched details for 1 CodeDeploy applications"
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
