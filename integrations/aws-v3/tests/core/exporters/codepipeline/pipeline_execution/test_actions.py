from unittest.mock import AsyncMock, call
import pytest

from aws.core.exporters.codepipeline.pipeline_execution.actions import (
    GetPipelineExecutionDetailsAction,
    ListPipelineExecutionsAction,
    CodePipelineExecutionActionInput,
)


class TestGetPipelineExecutionDetailsAction:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        # Arrange
        action = GetPipelineExecutionDetailsAction(AsyncMock())
        data = CodePipelineExecutionActionInput(
            items=[
                {"pipelineExecutionId": "execution-1"},
                {"pipelineExecutionId": "execution-2"},
                {"bad_data": "execution-3"},
            ],
            pipeline_name="pipeline-1",
        )

        action.client.get_pipeline_execution.side_effect = (
            lambda pipelineName, pipelineExecutionId: {
                "pipelineExecution": {
                    "pipelineName": pipelineName,
                    "pipelineExecutionId": pipelineExecutionId,
                    "status": "Succeeded",
                }
            }
        )

        # Act
        result = await action.execute(data)

        # Assert
        assert result == [
            {
                "pipelineName": data.pipeline_name,
                "pipelineExecutionId": data.items[0]["pipelineExecutionId"],
                "status": "Succeeded",
            },
            {
                "pipelineName": data.pipeline_name,
                "pipelineExecutionId": data.items[1]["pipelineExecutionId"],
                "status": "Succeeded",
            },
            {},
        ]

        action.client.get_pipeline_execution.assert_has_calls(
            [
                call(
                    pipelineName=data.pipeline_name,
                    pipelineExecutionId=data.items[0]["pipelineExecutionId"],
                ),
                call(
                    pipelineName=data.pipeline_name,
                    pipelineExecutionId=data.items[1]["pipelineExecutionId"],
                ),
            ]
        )


class TestListPipelineExecutionsAction:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        # Arrange
        action = ListPipelineExecutionsAction(AsyncMock())
        data = CodePipelineExecutionActionInput(
            items=[
                {"pipelineExecutionId": "execution-1"},
                {"pipelineExecutionId": "execution-2"},
                {"bad_data": "execution-3"},
            ],
            pipeline_name="pipeline-1",
        )

        # Act
        result = await action.execute(data)

        # Assert
        assert result == data.items
