from typing import Any
from unittest.mock import AsyncMock, call
import pytest

from aws.core.exporters.codedeploy.deployment.actions import (
    GetDeploymentAction,
    ListDeploymentsAction,
)


class TestGetDeploymentAction:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        # Arrange
        action = GetDeploymentAction(AsyncMock())
        deployments = ["d-1", "d-2", "d-3"]
        deployment_one = {"deploymentId": deployments[0], "status": "Succeeded"}
        deployment_three = {"deploymentId": deployments[2], "status": "Succeeded"}

        def mock_get_deployment(deploymentId: str) -> dict[str, Any]:
            if deploymentId == deployments[0]:
                return {"deploymentInfo": deployment_one}
            if deploymentId == deployments[2]:
                return {"deploymentInfo": deployment_three}
            raise Exception("boom")

        action.client.get_deployment.side_effect = mock_get_deployment

        # Act
        result = await action._execute(deployments)

        # Assert
        assert result == [deployment_one, {}, deployment_three]
        action.client.get_deployment.assert_has_calls(
            calls=[call(deploymentId=deployment) for deployment in deployments]
        )


class TestListDeploymentsAction:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        # Arrange
        action = ListDeploymentsAction(AsyncMock())
        deployments = ["d-1", "d-2", "d-3"]

        # Act
        result = await action._execute(deployments)

        # Assert
        assert result == [
            {"deploymentId": "d-1"},
            {"deploymentId": "d-2"},
            {"deploymentId": "d-3"},
        ]
