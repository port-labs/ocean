from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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


def make_mock_run() -> MagicMock:
    run = MagicMock()
    run.id = "run-1"
    run.execution_properties = {"reportPipelineStatus": True}
    return run


@pytest.mark.asyncio
class TestTriggerPipelineWebhookProcessor:
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
            payload={
                "object_kind": "pipeline",
                "object_attributes": {"status": "success"},
            },
        )
        assert await processor.should_process_event(event) is False

    async def test_handle_event_completes_run(
        self, processor: TriggerPipelineWebhookProcessor
    ) -> None:
        run = make_mock_run()
        resource_config = MagicMock()
        with (
            patch(
                "gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor.find_run_with_retry",
                AsyncMock(return_value=run),
            ),
            patch(
                "gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor.complete_run_if_in_progress",
                AsyncMock(return_value=True),
            ) as mock_complete,
        ):
            await processor.handle_event(make_event("success").payload, resource_config)

            mock_complete.assert_called_once_with(
                run, "success", completion_source="webhook"
            )

    async def test_handle_event_no_run_skips(
        self, processor: TriggerPipelineWebhookProcessor
    ) -> None:
        resource_config = MagicMock()
        with (
            patch(
                "gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor.find_run_with_retry",
                AsyncMock(return_value=None),
            ),
            patch(
                "gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor.complete_run_if_in_progress",
                AsyncMock(),
            ) as mock_complete,
        ):
            result = await processor.handle_event(
                make_event("success").payload, resource_config
            )

            mock_complete.assert_not_called()
            assert result.updated_raw_results == []
