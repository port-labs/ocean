from unittest.mock import AsyncMock
import pytest

from aws.core.exporters.codedeploy.deployment_target.actions import (
    GetDeploymentTargetDetailsAction,
    DeploymentTargetActionInput,
)


class TestGetDeploymentTargetDetailsAction:
    @pytest.fixture
    def action(self) -> GetDeploymentTargetDetailsAction:
        """Create a GetDeploymentTargetDetailsAction instance for testing."""
        return GetDeploymentTargetDetailsAction(AsyncMock())

    @pytest.mark.asyncio
    async def test_execute_instance_target_success(
        self, action: GetDeploymentTargetDetailsAction
    ) -> None:
        # Arrange
        resources = DeploymentTargetActionInput(
            deployment_id="d-EXAMPLE11",
            items=["i-0123456789abcdef0"],
        )

        mock_target = {
            "deploymentTargetType": "instanceTarget",
            "instanceTarget": {
                "deploymentId": "d-EXAMPLE11",
                "targetId": "i-0123456789abcdef0",
                "targetArn": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                "lastUpdatedAt": "2026-06-03T16:10:48.108000+00:00",
                "status": "Succeeded",
                "lifecycleEvents": [
                    {
                        "lifecycleEventName": "ApplicationStop",
                        "status": "Succeeded",
                    }
                ],
            },
        }
        action.client.batch_get_deployment_targets.return_value = {
            "deploymentTargets": [mock_target]
        }

        # Act
        result = await action._execute(resources)

        # Assert
        assert result == [{**mock_target, 'deploymentId': resources.deployment_id}]

        action.client.batch_get_deployment_targets.assert_called_once_with(
            deploymentId=resources.deployment_id,
            targetIds=resources.items,
        )
