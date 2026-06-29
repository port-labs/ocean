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
        assert len(result) == 1
        entry = result[0]
        assert entry["DeploymentId"] == "d-EXAMPLE11"
        assert entry["DeploymentTargetType"] == "instanceTarget"
        assert entry["TargetId"] == "i-0123456789abcdef0"
        assert (
            entry["TargetArn"]
            == "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"
        )
        assert entry["Status"] == "Succeeded"
        assert len(entry["LifecycleEvents"]) == 1
        action.client.batch_get_deployment_targets.assert_called_once_with(
            deploymentId=resources.deployment_id,
            targetIds=resources.items,
        )

    @pytest.mark.asyncio
    async def test_execute_empty_targets(
        self, action: GetDeploymentTargetDetailsAction
    ) -> None:
        # Arrange
        resources = DeploymentTargetActionInput(
            deployment_id="d-EXAMPLE11",
            items=["i-0123456789abcdef0"],
        )
        action.client.batch_get_deployment_targets.return_value = {}

        # Act
        result = await action._execute(resources)

        # Assert
        assert result == []
        action.client.batch_get_deployment_targets.assert_called_once_with(
            deploymentId=resources.deployment_id,
            targetIds=resources.items,
        )

    @pytest.mark.asyncio
    async def test_execute_multiple_targets(
        self, action: GetDeploymentTargetDetailsAction
    ) -> None:
        # Arrange
        resources = DeploymentTargetActionInput(
            deployment_id="d-EXAMPLE11",
            items=["i-0000000000000001", "i-0000000000000002"],
        )

        mock_targets = [
            {
                "deploymentTargetType": "instanceTarget",
                "instanceTarget": {
                    "deploymentId": "d-EXAMPLE11",
                    "targetId": "i-0000000000000001",
                    "status": "Succeeded",
                    "lifecycleEvents": [],
                },
            },
            {
                "deploymentTargetType": "instanceTarget",
                "instanceTarget": {
                    "deploymentId": "d-EXAMPLE11",
                    "targetId": "i-0000000000000002",
                    "status": "Failed",
                    "lifecycleEvents": [],
                },
            },
        ]
        action.client.batch_get_deployment_targets.return_value = {
            "deploymentTargets": mock_targets
        }

        # Act
        result = await action._execute(resources)

        # Assert
        assert len(result) == 2
        assert result[0]["TargetId"] == "i-0000000000000001"
        assert result[0]["Status"] == "Succeeded"
        assert result[1]["TargetId"] == "i-0000000000000002"
        assert result[1]["Status"] == "Failed"

    @pytest.mark.asyncio
    async def test_execute_lambda_target(
        self, action: GetDeploymentTargetDetailsAction
    ) -> None:
        # Arrange
        resources = DeploymentTargetActionInput(
            deployment_id="d-EXAMPLE22",
            items=["my-lambda-function:1"],
        )

        mock_target = {
            "deploymentTargetType": "lambdaTarget",
            "lambdaTarget": {
                "deploymentId": "d-EXAMPLE22",
                "targetId": "my-lambda-function:1",
                "targetArn": "arn:aws:lambda:us-east-1:123456789012:function:my-lambda-function:1",
                "status": "Succeeded",
                "lastUpdatedAt": "2026-06-03T16:10:48.108000+00:00",
                "lifecycleEvents": [],
            },
        }
        action.client.batch_get_deployment_targets.return_value = {
            "deploymentTargets": [mock_target]
        }

        # Act
        result = await action._execute(resources)

        # Assert
        assert len(result) == 1
        entry = result[0]
        assert entry["DeploymentTargetType"] == "lambdaTarget"
        assert entry["TargetId"] == "my-lambda-function:1"
        assert "LambdaTarget" in entry
