import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor import (
    TriggerPipelineWebhookProcessor,
)


def make_event(status: str, object_kind: str = "pipeline") -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        headers={"x-gitlab-event": "Pipeline Hook"},
        payload={
            "object_kind": object_kind,
            "object_attributes": {"id": 99, "status": status},
            "project": {"id": 42},
        },
    )


@pytest.fixture
def processor() -> TriggerPipelineWebhookProcessor:
    return TriggerPipelineWebhookProcessor(event=make_event("success"))


def make_mock_run(in_progress: bool = True, report_status: bool = True) -> MagicMock:
    run = MagicMock()
    run.id = "run-1"
    run.execution_properties = {"reportPipelineStatus": report_status}
    return run


@pytest.mark.asyncio
class TestTriggerPipelineWebhookProcessor:
    # --- should_process_event ---

    async def test_should_process_terminal_status(
        self, processor: TriggerPipelineWebhookProcessor
    ) -> None:
        for status in ("success", "failed", "canceled", "skipped"):
            assert await processor.should_process_event(make_event(status)) is True

    async def test_should_not_process_in_progress_status(
        self, processor: TriggerPipelineWebhookProcessor
    ) -> None:
        for status in ("running", "pending", "created"):
            assert await processor.should_process_event(make_event(status)) is False

    async def test_should_not_process_wrong_hook(
        self, processor: TriggerPipelineWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="t",
            headers={"x-gitlab-event": "Job Hook"},
            payload={"object_kind": "pipeline", "object_attributes": {"status": "success"}},
        )
        assert await processor.should_process_event(event) is False

    # --- handle_event ---

    async def test_terminal_success_completes_run(
        self, processor: TriggerPipelineWebhookProcessor
    ) -> None:
        run = make_mock_run()
        resource_config = MagicMock()
        with patch(
            "gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress.return_value = True
            mock_ocean.port_client.report_run_completed = AsyncMock()

            payload = make_event("success").payload
            await processor.handle_event(payload, resource_config)

            mock_ocean.port_client.report_run_completed.assert_called_once_with(
                run, True, "Pipeline completed: success"
            )

    @pytest.mark.parametrize("status", ["failed", "canceled", "skipped"])
    async def test_terminal_non_success_fails_run(
        self, processor: TriggerPipelineWebhookProcessor, status: str
    ) -> None:
        run = make_mock_run()
        resource_config = MagicMock()
        with patch(
            "gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress.return_value = True
            mock_ocean.port_client.report_run_completed = AsyncMock()

            payload = make_event(status).payload
            await processor.handle_event(payload, resource_config)

            mock_ocean.port_client.report_run_completed.assert_called_once_with(
                run, False, f"Pipeline completed: {status}"
            )

    async def test_no_matching_run_skips_silently(
        self, processor: TriggerPipelineWebhookProcessor
    ) -> None:
        resource_config = MagicMock()
        with patch(
            "gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=None)
            mock_ocean.port_client.report_run_completed = AsyncMock()

            result = await processor.handle_event(make_event("success").payload, resource_config)

            mock_ocean.port_client.report_run_completed.assert_not_called()
            assert result.updated_raw_results == []

    async def test_duplicate_webhook_ignored(
        self, processor: TriggerPipelineWebhookProcessor
    ) -> None:
        run = make_mock_run()
        resource_config = MagicMock()
        with patch(
            "gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress.return_value = False
            mock_ocean.port_client.report_run_completed = AsyncMock()

            await processor.handle_event(make_event("success").payload, resource_config)

            mock_ocean.port_client.report_run_completed.assert_not_called()

    async def test_report_pipeline_status_false_skips(
        self, processor: TriggerPipelineWebhookProcessor
    ) -> None:
        run = make_mock_run(report_status=False)
        resource_config = MagicMock()
        with patch(
            "gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.report_run_completed = AsyncMock()

            await processor.handle_event(make_event("success").payload, resource_config)

            mock_ocean.port_client.report_run_completed.assert_not_called()
