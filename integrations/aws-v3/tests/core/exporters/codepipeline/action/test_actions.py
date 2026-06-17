from typing import Any
from unittest.mock import AsyncMock, call
import pytest

from aws.core.exporters.codepipeline.action.actions import (
    GetPipelineActionsDetails,
    CodePipelinePipelineActionInput,
)


class TestGetPipelineActionsDetails:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        # Arrange
        action = GetPipelineActionsDetails(AsyncMock())

        pipeline_success: dict[str, Any] = {
            "name": "one",
            "metadata": {"pipelineArn": "arn1"},
            "pipeline": {
                "version": 1,
                "stages": [
                    {
                        "name": "stage_one",
                        "actions": [
                            {"name": "action_one"},
                            {"name": "action_two"},
                        ],
                    },
                    {"name": "stage_two", "actions": [{"name": "action_three"}]},
                ],
            },
        }
        pipeline_with_no_stages = {"name": "three"}
        pipeline_with_no_actions = {
            "name": "four",
            "pipeline": {"stages": [{"name": "empty_stage"}]},
        }
        pipeline_error = {"name": "five"}
        pipelines = [
            pipeline_success,
            pipeline_with_no_stages,
            pipeline_with_no_actions,
        ]

        def mock_get_pipeline(name: str) -> dict[str, Any]:
            return next(pipeline for pipeline in pipelines if pipeline["name"] == name)

        action.client.get_pipeline.side_effect = mock_get_pipeline

        # Execute the action
        result = await action._execute(
            CodePipelinePipelineActionInput(
                items=[{"name": pipeline["name"]} for pipeline in pipelines]
                + [pipeline_error],
                region="region",
                account_id="account_id",
            )
        )

        # Verify the results
        assert result == [
            {
                "name": pipeline_success["pipeline"]["stages"][0]["actions"][0]["name"],
                "pipelineArn": pipeline_success["metadata"]["pipelineArn"],
                "pipelineName": pipeline_success["name"],
                "pipelineVersion": pipeline_success["pipeline"]["version"],
                "stageName": pipeline_success["pipeline"]["stages"][0]["name"],
            },
            {
                "name": pipeline_success["pipeline"]["stages"][0]["actions"][1]["name"],
                "pipelineArn": pipeline_success["metadata"]["pipelineArn"],
                "pipelineName": pipeline_success["name"],
                "pipelineVersion": pipeline_success["pipeline"]["version"],
                "stageName": pipeline_success["pipeline"]["stages"][0]["name"],
            },
            {
                "name": pipeline_success["pipeline"]["stages"][1]["actions"][0]["name"],
                "pipelineArn": pipeline_success["metadata"]["pipelineArn"],
                "pipelineName": pipeline_success["name"],
                "pipelineVersion": pipeline_success["pipeline"]["version"],
                "stageName": pipeline_success["pipeline"]["stages"][1]["name"],
            },
        ]
        action.client.get_pipeline.assert_has_calls(
            [call(name=pipeline["name"]) for pipeline in pipelines]
            + [call(name=pipeline_error["name"])]
        )
