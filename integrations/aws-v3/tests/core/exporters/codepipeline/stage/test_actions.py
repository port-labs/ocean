from typing import Any
from unittest.mock import AsyncMock, call
import pytest

from aws.core.exporters.codepipeline.stage.actions import (
    GetPipelineStagesAction,
    GetPipelineStagesInput,
)


class TestGetPipelineStagesAction:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        # Arrange
        action = GetPipelineStagesAction(AsyncMock())

        pipeline_success: dict[str, Any] = {
            "name": "one",
            "metadata": {"pipelineArn": "arn1"},
            "pipeline": {
                "version": 1,
                "stages": [
                    {
                        "name": "stage_one",
                        "actions": [{"name": "action_one"}],
                    },
                    {"name": "stage_two", "actions": [{"name": "action_two"}]},
                ],
            },
        }
        pipeline_with_no_stages = {"name": "three"}
        pipeline_with_empty_stages = {
            "name": "four",
            "pipeline": {"stages": []},
        }
        pipeline_error = {"name": "five"}
        pipelines = [
            pipeline_success,
            pipeline_with_no_stages,
            pipeline_with_empty_stages,
        ]

        def mock_get_pipeline(name: str):
            return next(pipeline for pipeline in pipelines if pipeline["name"] == name)

        action.client.get_pipeline.side_effect = mock_get_pipeline

        # Execute the action
        result = await action._execute(
            GetPipelineStagesInput(
                items=[{"name": pipeline["name"]} for pipeline in pipelines]
                + [pipeline_error],
                region="region",
                account_id="account_id",
            )
        )

        # Verify the results
        assert result == [
            {
                "name": pipeline_success["pipeline"]["stages"][0]["name"],
                "actions": pipeline_success["pipeline"]["stages"][0]["actions"],
                "pipelineName": pipeline_success["name"],
                "pipelineArn": pipeline_success["metadata"]["pipelineArn"],
                "order": 1,
            },
            {
                "name": pipeline_success["pipeline"]["stages"][1]["name"],
                "actions": pipeline_success["pipeline"]["stages"][1]["actions"],
                "pipelineName": pipeline_success["name"],
                "pipelineArn": pipeline_success["metadata"]["pipelineArn"],
                "order": 2,
            },
        ]
        action.client.get_pipeline.assert_has_calls(
            [call(name=pipeline["name"]) for pipeline in pipelines]
            + [call(name=pipeline_error["name"])]
        )
