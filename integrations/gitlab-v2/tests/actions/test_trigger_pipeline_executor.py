import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import WorkflowNodeRun, WorkflowNodeRunStatus

from gitlab.actions.trigger_pipeline_executor import TriggerPipelineExecutor
from gitlab.helpers.exceptions import (
    GitlabTriggerPipelineError,
    MissingExecutionPropertyError,
)

PIPELINE_RESPONSE = {
    "id": 99,
    "project_id": 42,
    "web_url": "https://gitlab.com/my-group/my-project/-/pipelines/99",
    "status": "pending",
}


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        identifier="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        node={
            "config": {
                "integrationInvocationType": "trigger_pipeline",
                "integrationActionExecutionProperties": execution_properties,
            },
        },
    )


@pytest.fixture
def executor() -> TriggerPipelineExecutor:
    with patch("gitlab.actions.abstract_gitlab_executor.create_gitlab_client"):
        ex = TriggerPipelineExecutor()
        ex.client = MagicMock()
        ex.client.trigger_pipeline = AsyncMock(return_value=PIPELINE_RESPONSE)
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.update_run_started = AsyncMock()
    client.report_run_completed = AsyncMock()
    client.post_run_log = AsyncMock()
    return client


@pytest.mark.asyncio
class TestTriggerPipelineExecutor:
    async def test_happy_path(
        self, executor: TriggerPipelineExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run({"project": "my-group/my-project", "ref": "main"})
        with patch("gitlab.actions.trigger_pipeline_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        executor.client.trigger_pipeline.assert_called_once_with(  # type: ignore[attr-defined]
            "my-group/my-project", "main", []
        )
        mock_port_client.update_run_started.assert_called_once_with(
            run,
            PIPELINE_RESPONSE["web_url"],
            "gl_42_99",
        )
        mock_port_client.report_run_completed.assert_not_called()
        mock_port_client.post_run_log.assert_called()

    async def test_report_pipeline_status_false_completes_immediately(
        self, executor: TriggerPipelineExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "ref": "main",
                "reportPipelineStatus": False,
            }
        )
        with patch("gitlab.actions.trigger_pipeline_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_port_client.update_run_started.assert_called_once()
        mock_port_client.report_run_completed.assert_called_once_with(
            run, True, "Pipeline triggered successfully"
        )

    async def test_missing_project_raises(
        self, executor: TriggerPipelineExecutor
    ) -> None:
        run = make_run({"ref": "main"})
        with pytest.raises(MissingExecutionPropertyError, match="project is required"):
            await executor.execute(run)

    async def test_missing_ref_raises(self, executor: TriggerPipelineExecutor) -> None:
        run = make_run({"project": "my-group/my-project"})
        with pytest.raises(MissingExecutionPropertyError, match="ref is required"):
            await executor.execute(run)

    async def test_api_error_raises_trigger_error(
        self, executor: TriggerPipelineExecutor
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "403 Forbidden"}
        executor.client.trigger_pipeline = AsyncMock(  # type: ignore[method-assign]
            side_effect=httpx.HTTPStatusError(
                "403",
                request=MagicMock(),
                response=mock_response,
            ),
        )
        run = make_run({"project": "my-group/my-project", "ref": "main"})
        with patch("gitlab.actions.trigger_pipeline_executor.ocean") as mock_ocean:
            mock_ocean.port_client = MagicMock()
            mock_ocean.port_client.post_run_log = AsyncMock()
            with pytest.raises(GitlabTriggerPipelineError, match="403 Forbidden"):
                await executor.execute(run)

    async def test_incomplete_response_raises(
        self, executor: TriggerPipelineExecutor
    ) -> None:
        executor.client.trigger_pipeline = AsyncMock(  # type: ignore[method-assign]
            return_value={"id": 99},
        )
        run = make_run({"project": "my-group/my-project", "ref": "main"})
        with patch("gitlab.actions.trigger_pipeline_executor.ocean") as mock_ocean:
            mock_ocean.port_client = MagicMock()
            mock_ocean.port_client.post_run_log = AsyncMock()
            with pytest.raises(GitlabTriggerPipelineError, match="empty or incomplete"):
                await executor.execute(run)

    async def test_pipeline_variables_null_treated_as_empty(
        self, executor: TriggerPipelineExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "ref": "main",
                "pipelineVariables": None,
            }
        )
        with patch("gitlab.actions.trigger_pipeline_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)
        executor.client.trigger_pipeline.assert_called_once_with(  # type: ignore[attr-defined]
            "my-group/my-project", "main", []
        )

    async def test_pipeline_variables_non_dict_raises(
        self, executor: TriggerPipelineExecutor
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "ref": "main",
                "pipelineVariables": ["a", "b"],
            }
        )
        with pytest.raises(
            MissingExecutionPropertyError,
            match="pipelineVariables must be a key-value object",
        ):
            await executor.execute(run)

    async def test_pipeline_variables_serialized(
        self, executor: TriggerPipelineExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run(
            {
                "project": "my-group/my-project",
                "ref": "main",
                "pipelineVariables": {"ENV": "prod", "COUNT": 3, "FLAG": True},
            }
        )
        with patch("gitlab.actions.trigger_pipeline_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        call_args = executor.client.trigger_pipeline.call_args  # type: ignore[attr-defined]
        _, call_ref, call_vars = call_args[0]
        assert call_ref == "main"
        vars_by_key = {v["key"]: v["value"] for v in call_vars}
        assert vars_by_key["ENV"] == "prod"
        assert vars_by_key["COUNT"] == json.dumps(3)
        assert vars_by_key["FLAG"] == json.dumps(True)
