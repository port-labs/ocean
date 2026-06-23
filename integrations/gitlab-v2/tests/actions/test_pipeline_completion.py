from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import WorkflowNodeRun, WorkflowNodeRunStatus

from gitlab.actions.pipeline_completion import (
    complete_run_from_pipeline_status,
    find_run_with_retry,
)

EXTERNAL_ID = "gl_42_99"


def make_run(report_status: bool = True) -> MagicMock:
    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run-1"
    run.status = WorkflowNodeRunStatus.IN_PROGRESS
    run.execution_properties = {"reportPipelineStatus": report_status}
    return run


@pytest.mark.asyncio
class TestFindRunWithRetry:
    async def test_returns_run_on_first_try(self) -> None:
        run = make_run()
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            result = await find_run_with_retry(EXTERNAL_ID)

        assert result is run

    async def test_retries_until_found(self) -> None:
        run = make_run()
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(
                side_effect=[None, None, run]
            )
            with patch(
                "gitlab.actions.pipeline_completion.asyncio.sleep", AsyncMock()
            ) as mock_sleep:
                result = await find_run_with_retry(EXTERNAL_ID)

        assert result is run
        assert mock_sleep.await_count == 2

    async def test_returns_none_after_exhausting_retries(self) -> None:
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(
                return_value=None
            )
            with patch("gitlab.actions.pipeline_completion.asyncio.sleep", AsyncMock()):
                result = await find_run_with_retry(EXTERNAL_ID)

        assert result is None


@pytest.mark.asyncio
class TestCompleteRunFromPipelineStatus:
    async def test_completes_successful_pipeline(self) -> None:
        run = make_run()
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
            mock_ocean.port_client.report_run_completed = AsyncMock()

            result = await complete_run_from_pipeline_status(
                EXTERNAL_ID, "success", completion_source="webhook"
            )

        assert result is True
        mock_ocean.port_client.report_run_completed.assert_called_once_with(
            run, True, "Pipeline completed: success"
        )

    async def test_completes_failed_pipeline(self) -> None:
        run = make_run()
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
            mock_ocean.port_client.report_run_completed = AsyncMock()

            result = await complete_run_from_pipeline_status(
                EXTERNAL_ID, "failed", completion_source="webhook"
            )

        assert result is True
        mock_ocean.port_client.report_run_completed.assert_called_once_with(
            run, False, "Pipeline completed: failed"
        )

    async def test_skips_when_report_disabled(self) -> None:
        run = make_run(report_status=False)
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.report_run_completed = AsyncMock()

            result = await complete_run_from_pipeline_status(
                EXTERNAL_ID, "success", completion_source="webhook"
            )

        assert result is False
        mock_ocean.port_client.report_run_completed.assert_not_called()

    async def test_skips_when_already_completed(self) -> None:
        run = make_run()
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=False)
            mock_ocean.port_client.report_run_completed = AsyncMock()

            result = await complete_run_from_pipeline_status(
                EXTERNAL_ID, "success", completion_source="webhook"
            )

        assert result is False
        mock_ocean.port_client.report_run_completed.assert_not_called()

    async def test_skips_when_run_not_found(self) -> None:
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(
                return_value=None
            )
            mock_ocean.port_client.report_run_completed = AsyncMock()

            result = await complete_run_from_pipeline_status(
                EXTERNAL_ID, "success", completion_source="webhook"
            )

        assert result is False
        mock_ocean.port_client.report_run_completed.assert_not_called()

    async def test_treats_409_as_already_completed(self) -> None:
        run = make_run()
        response = MagicMock()
        response.status_code = 409
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
            mock_ocean.port_client.report_run_completed = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "409",
                    request=MagicMock(),
                    response=response,
                )
            )

            result = await complete_run_from_pipeline_status(
                EXTERNAL_ID, "success", completion_source="webhook"
            )

        assert result is False
