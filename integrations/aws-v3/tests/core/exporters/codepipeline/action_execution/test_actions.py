from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest

from aws.core.exporters.codepipeline.action_execution.actions import (
    GetActionExecutionsAction,
    CodePipelineActionExecutionInput,
)


class TestGetActionExecutionsAction:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        # Arrange
        action = GetActionExecutionsAction(AsyncMock())

        pipeline_one_executions = [
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
                "status": "Succeeded",
            },
        ]
        pipeline_two_executions = [
            {
                "actionExecutionId": "exec-3",
                "actionName": "Deploy",
                "stageName": "Deploy",
                "status": "InProgress",
            },
        ]

        mock_paginator = MagicMock()

        async def mock_paginate_one(**kwargs: Any):  # type: ignore
            yield {"actionExecutionDetails": pipeline_one_executions}

        async def mock_paginate_two(**kwargs: Any):  # type: ignore
            yield {"actionExecutionDetails": pipeline_two_executions}

        paginate_side_effects = [mock_paginate_one, mock_paginate_two]
        call_count = 0

        def get_paginator_side_effect(method_name: str) -> MagicMock:
            nonlocal call_count
            paginator = MagicMock()
            paginator.paginate = paginate_side_effects[call_count]
            call_count += 1
            return paginator

        action.client.get_paginator.side_effect = get_paginator_side_effect

        # Execute
        result = await action._execute(
            CodePipelineActionExecutionInput(
                items=[{"name": "pipeline-one"}, {"name": "pipeline-two"}],
                region="us-east-1",
                account_id="123456789012",
            )
        )

        # Verify
        assert len(result) == 3
        assert result[0]["actionExecutionId"] == "exec-1"
        assert result[0]["pipelineName"] == "pipeline-one"
        assert result[1]["actionExecutionId"] == "exec-2"
        assert result[1]["pipelineName"] == "pipeline-one"
        assert result[2]["actionExecutionId"] == "exec-3"
        assert result[2]["pipelineName"] == "pipeline-two"

    @pytest.mark.asyncio
    async def test_execute_with_error_skips_failed_pipeline(self) -> None:
        # Arrange
        action = GetActionExecutionsAction(AsyncMock())

        good_executions = [
            {
                "actionExecutionId": "exec-1",
                "actionName": "Source",
                "stageName": "Source",
                "status": "Succeeded",
            }
        ]

        call_count = 0

        async def mock_paginate_good(**kwargs: Any):  # type: ignore
            yield {"actionExecutionDetails": good_executions}

        async def mock_paginate_error(**kwargs: Any):  # type: ignore
            raise Exception("Access Denied")
            yield  # make it a generator  # noqa: unreachable

        def get_paginator_side_effect(method_name: str) -> MagicMock:
            nonlocal call_count
            paginator = MagicMock()
            if call_count == 0:
                paginator.paginate = mock_paginate_good
            else:
                paginator.paginate = mock_paginate_error
            call_count += 1
            return paginator

        action.client.get_paginator.side_effect = get_paginator_side_effect

        # Execute
        result = await action._execute(
            CodePipelineActionExecutionInput(
                items=[{"name": "pipeline-good"}, {"name": "pipeline-error"}],
                region="us-east-1",
                account_id="123456789012",
            )
        )

        # Verify - only the good pipeline's executions are returned
        assert len(result) == 1
        assert result[0]["actionExecutionId"] == "exec-1"
        assert result[0]["pipelineName"] == "pipeline-good"

    @pytest.mark.asyncio
    async def test_execute_empty_pipelines(self) -> None:
        # Arrange
        action = GetActionExecutionsAction(AsyncMock())

        # Execute
        result = await action._execute(
            CodePipelineActionExecutionInput(
                items=[],
                region="us-east-1",
                account_id="123456789012",
            )
        )

        # Verify
        assert result == []
        action.client.get_paginator.assert_not_called()
