from unittest.mock import AsyncMock
import pytest

from aws.core.exporters.codepipeline.action_execution.actions import (
    ListActionExecutionsAction,
)


class TestListActionExecutionsAction:
    @pytest.mark.asyncio
    async def test_execute_returns_resources(self) -> None:
        # Arrange
        action = ListActionExecutionsAction(AsyncMock())
        resources = [
            {
                "actionExecutionId": "exec-1",
                "actionName": "Source",
                "stageName": "Source",
                "status": "Succeeded",
            },
            {
                "actionExecutionId": "exec-2",
                "actionName": "Build",
                "stageName": "Build",
                "status": "InProgress",
            },
        ]

        # Act
        result = await action.execute(resources)

        # Assert
        assert result == resources
