from typing import Any
from unittest.mock import AsyncMock, call
import pytest

from aws.core.exporters.codedeploy.deployment_group.actions import (
    GetDeploymentGroupDetailsAction,
    GetDeploymentGroupTags,
    DeploymentGroupActionInput,
)


class TestGetDeploymentGroupDetailsAction:
    @pytest.fixture
    def action(
        self,
    ) -> GetDeploymentGroupDetailsAction:
        """Create a GetDeploymentGroupDetailsAction instance for testing."""
        return GetDeploymentGroupDetailsAction(AsyncMock())

    @pytest.mark.asyncio
    async def test_execute_success(
        self, action: GetDeploymentGroupDetailsAction
    ) -> None:
        # Arrange
        resources = DeploymentGroupActionInput(
            app_name="my-app",
            groups=["group-a", "group-b"],
            region="region",
            account_id="account_id",
        )

        mock_response_one = {"deploymentGroupName": "group-a"}
        mock_response_two = {"deploymentGroupName": "group-b"}
        action.client.batch_get_deployment_groups.return_value = {
            "deploymentGroupsInfo": [mock_response_one, mock_response_two]
        }

        # Act
        result = await action._execute(resources)

        # Assert
        assert result == [mock_response_one, mock_response_two]
        action.client.batch_get_deployment_groups.assert_called_once_with(
            applicationName=resources.app_name,
            deploymentGroupNames=resources.groups,
        )

    @pytest.mark.asyncio
    async def test_execute_empty_deployment_groups_info(
        self, action: GetDeploymentGroupDetailsAction
    ) -> None:
        # Arrange
        resources: DeploymentGroupActionInput = DeploymentGroupActionInput(
            app_name="my-app",
            groups=["group-a", "group-b"],
            region="region",
            account_id="account_id",
        )
        action.client.batch_get_deployment_groups.return_value = {}

        # Act
        result = await action._execute(resources)

        # Assert
        assert result == []
        action.client.batch_get_deployment_groups.assert_called_once_with(
            applicationName=resources.app_name,
            deploymentGroupNames=resources.groups,
        )


class TestGetDeploymentGroupTags:
    @pytest.fixture
    def action(self) -> GetDeploymentGroupTags:
        """Create a GetDeploymentGroupTags instance for testing."""
        return GetDeploymentGroupTags(AsyncMock())

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetDeploymentGroupTags) -> None:
        # Arrange
        resources: DeploymentGroupActionInput = DeploymentGroupActionInput(
            app_name="my-app",
            groups=["group-a", "group-b", "group-c"],
            region="region",
            account_id="account_id",
        )

        def mock_list_tags(ResourceArn: str) -> dict[str, Any]:
            if ResourceArn.endswith(f"{resources.app_name}/{resources.groups[0]}"):
                return {"Tags": [{"Key": "Environment", "Value": "production"}]}
            if ResourceArn.endswith(f"{resources.app_name}/{resources.groups[1]}"):
                return {"Tags": [{"Key": "Environment", "Value": "staging"}]}
            raise Exception

        action.client.list_tags_for_resource.side_effect = mock_list_tags

        # Act
        result = await action._execute(resources)

        # Assert
        assert result == [
            {"Tags": [{"Key": "Environment", "Value": "production"}]},
            {"Tags": [{"Key": "Environment", "Value": "staging"}]},
            {},
        ]

        action.client.list_tags_for_resource.assert_has_calls(
            calls=[
                call(
                    ResourceArn=f"arn:aws:codedeploy:{resources.region}:{resources.account_id}:deploymentgroup:{resources.app_name}/{group}"
                )
                for group in resources.groups
            ]
        )
