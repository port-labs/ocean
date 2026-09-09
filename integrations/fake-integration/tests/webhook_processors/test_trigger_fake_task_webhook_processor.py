from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from actions.constants import TASK_STATUS_LABELS
from webhook_processors.trigger_fake_task_webhook_processor import (
    TriggerFakeTaskWebhookProcessor,
)


def make_event(payload: dict[str, object]) -> WebhookEvent:
    return WebhookEvent(
        trace_id="trace-1",
        payload=payload,
        headers={},
    )


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.find_run_by_external_id = AsyncMock()
    client.is_run_in_progress = MagicMock(return_value=True)
    client.post_run_log = AsyncMock()
    client.report_run_completed = AsyncMock()
    return client


@pytest.mark.asyncio
class TestTriggerFakeTaskWebhookProcessor:
    async def test_completes_matching_run(self, mock_port_client: MagicMock) -> None:
        run = MagicMock()
        run.id = "run-1"
        run.execution_properties = {"reportTaskStatus": True}
        mock_port_client.find_run_by_external_id.return_value = run

        event = make_event(
            {
                "event": "fake_task.completed",
                "task": {"id": "task-123", "status": "success"},
            }
        )
        processor = TriggerFakeTaskWebhookProcessor(event)

        with patch(
            "webhook_processors.trigger_fake_task_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await processor.handle_event(event.payload, MagicMock(spec=ResourceConfig))

        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            True,
            "Fake task completed: success",
            status_label=TASK_STATUS_LABELS["success"],
        )

    async def test_skips_non_terminal_status(self, mock_port_client: MagicMock) -> None:
        event = make_event(
            {
                "event": "fake_task.completed",
                "task": {"id": "task-123", "status": "pending"},
            }
        )
        processor = TriggerFakeTaskWebhookProcessor(event)

        with patch(
            "webhook_processors.trigger_fake_task_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await processor.handle_event(event.payload, MagicMock(spec=ResourceConfig))

        mock_port_client.find_run_by_external_id.assert_not_awaited()
