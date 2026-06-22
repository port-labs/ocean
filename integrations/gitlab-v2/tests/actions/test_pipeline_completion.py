from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import WorkflowNodeRun, WorkflowNodeRunStatus

from gitlab.actions.pipeline_completion import (
    complete_run_from_pipeline_status,
    find_run_with_retry,
    poll_pipeline_to_completion,
)


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
            result = await find_run_with_retry("gl_42_99")

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
                result = await find_run_with_retry("gl_42_99")

        assert result is run
        assert mock_sleep.await_count == 2

    async def test_returns_none_after_exhausting_retries(self) -> None:
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(
                return_value=None
            )
            with patch("gitlab.actions.pipeline_completion.asyncio.sleep", AsyncMock()):
                result = await find_run_with_retry("gl_42_99")

        assert result is None


@pytest.mark.asyncio
class TestCompleteRunFromPipelineStatus:
    async def test_completes_successful_pipeline(self) -> None:
        run = make_run()
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
            mock_ocean.port_client.report_run_completed = AsyncMock()

            result = await complete_run_from_pipeline_status(
                run, "success", completion_source="webhook"
            )

        assert result is True
        mock_ocean.port_client.report_run_completed.assert_called_once_with(
            run, True, "Pipeline completed: success"
        )

    async def test_completes_failed_pipeline(self) -> None:
        run = make_run()
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
            mock_ocean.port_client.report_run_completed = AsyncMock()

            result = await complete_run_from_pipeline_status(
                run, "failed", completion_source="poll"
            )

        assert result is True
        mock_ocean.port_client.report_run_completed.assert_called_once_with(
            run, False, "Pipeline completed: failed"
        )

    async def test_skips_when_report_disabled(self) -> None:
        run = make_run(report_status=False)
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.report_run_completed = AsyncMock()

            result = await complete_run_from_pipeline_status(
                run, "success", completion_source="webhook"
            )

        assert result is False
        mock_ocean.port_client.report_run_completed.assert_not_called()

    async def test_skips_when_already_completed(self) -> None:
        run = make_run()
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=False)
            mock_ocean.port_client.report_run_completed = AsyncMock()

            result = await complete_run_from_pipeline_status(
                run, "success", completion_source="poll"
            )

        assert result is False
        mock_ocean.port_client.report_run_completed.assert_not_called()


@pytest.mark.asyncio
class TestPollPipelineToCompletion:
    async def test_completes_on_terminal_status(self) -> None:
        run = make_run()
        get_pipeline = AsyncMock(return_value={"status": "success"})
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
            mock_ocean.port_client.report_run_completed = AsyncMock()

            await poll_pipeline_to_completion(
                external_id="gl_42_99",
                project_id=42,
                pipeline_id=99,
                get_pipeline=get_pipeline,
            )

        get_pipeline.assert_called_once_with(42, 99)
        mock_ocean.port_client.report_run_completed.assert_called_once_with(
            run, True, "Pipeline completed: success"
        )

    async def test_exits_when_run_already_completed_by_webhook(self) -> None:
        run = make_run()
        get_pipeline = AsyncMock(return_value={"status": "running"})
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=False)
            mock_ocean.port_client.report_run_completed = AsyncMock()
            with patch(
                "gitlab.actions.pipeline_completion.asyncio.sleep", AsyncMock()
            ) as mock_sleep:
                await poll_pipeline_to_completion(
                    external_id="gl_42_99",
                    project_id=42,
                    pipeline_id=99,
                    get_pipeline=get_pipeline,
                )

        mock_sleep.assert_not_called()
        mock_ocean.port_client.report_run_completed.assert_not_called()

    async def test_exits_when_run_not_found(self) -> None:
        get_pipeline = AsyncMock(return_value={"status": "running"})
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(
                return_value=None
            )
            mock_ocean.port_client.report_run_completed = AsyncMock()
            with patch(
                "gitlab.actions.pipeline_completion.asyncio.sleep", AsyncMock()
            ) as mock_sleep:
                await poll_pipeline_to_completion(
                    external_id="gl_42_99",
                    project_id=42,
                    pipeline_id=99,
                    get_pipeline=get_pipeline,
                )

        mock_sleep.assert_not_called()
        mock_ocean.port_client.report_run_completed.assert_not_called()

    async def test_skips_gitlab_poll_after_webhook_completes_during_sleep(self) -> None:
        run = make_run()
        get_pipeline = AsyncMock(return_value={"status": "running"})
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress = MagicMock(
                side_effect=[True, False]
            )
            mock_ocean.port_client.report_run_completed = AsyncMock()
            with patch(
                "gitlab.actions.pipeline_completion.asyncio.sleep", AsyncMock()
            ) as mock_sleep:
                await poll_pipeline_to_completion(
                    external_id="gl_42_99",
                    project_id=42,
                    pipeline_id=99,
                    get_pipeline=get_pipeline,
                    timeout=60,
                )

        get_pipeline.assert_called_once_with(42, 99)
        mock_sleep.assert_awaited_once()
        mock_ocean.port_client.report_run_completed.assert_not_called()

    async def test_retries_after_get_pipeline_error(self) -> None:
        run = make_run()
        get_pipeline = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError("503", request=MagicMock(), response=MagicMock()),
                {"status": "success"},
            ]
        )
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
            mock_ocean.port_client.report_run_completed = AsyncMock()
            with patch(
                "gitlab.actions.pipeline_completion.asyncio.sleep", AsyncMock()
            ) as mock_sleep:
                await poll_pipeline_to_completion(
                    external_id="gl_42_99",
                    project_id=42,
                    pipeline_id=99,
                    get_pipeline=get_pipeline,
                    timeout=60,
                )

        assert get_pipeline.await_count == 2
        mock_sleep.assert_awaited_once()
        mock_ocean.port_client.report_run_completed.assert_called_once()

    async def test_reports_failure_on_unexpected_error(self) -> None:
        run = make_run()
        with patch("gitlab.actions.pipeline_completion.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
            mock_ocean.port_client.report_run_failure = AsyncMock()
            with patch(
                "gitlab.actions.pipeline_completion.complete_run_from_pipeline_status",
                AsyncMock(side_effect=RuntimeError("boom")),
            ):
                await poll_pipeline_to_completion(
                    external_id="gl_42_99",
                    project_id=42,
                    pipeline_id=99,
                    get_pipeline=AsyncMock(return_value={"status": "success"}),
                )

        mock_ocean.port_client.report_run_failure.assert_called_once()
