from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_devops.client.azure_devops_client import PIPELINES_PUBLISHER_ID
from azure_devops.webhooks.events import PipelineRunEvents
from azure_devops.webhooks.webhook_processors.pipeline_run_action_webhook_processor import (
    PipelineRunActionWebhookProcessor,
)
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

PROCESSOR_MODULE = (
    "azure_devops.webhooks.webhook_processors."
    "pipeline_run_action_webhook_processor.ocean"
)


def _payload(state: str = "completed", result: str = "succeeded") -> dict[str, Any]:
    return {
        "publisherId": PIPELINES_PUBLISHER_ID,
        "eventType": PipelineRunEvents.PIPELINE_RUN_STATE_CHANGED,
        "resourceContainers": {"project": {"id": "proj-guid"}},
        "resource": {
            "pipeline": {"id": 12},
            "run": {"id": 4567, "state": state, "result": result},
        },
    }


def _mock_ocean(
    monkeypatch: pytest.MonkeyPatch,
    *,
    port_run: Any,
    in_progress: bool = True,
) -> MagicMock:
    mock_ocean = MagicMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=port_run)
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=in_progress)
    mock_ocean.port_client.report_run_completed = AsyncMock()
    monkeypatch.setattr(PROCESSOR_MODULE, mock_ocean)
    return mock_ocean


@pytest.fixture
def processor(event: WebhookEvent) -> PipelineRunActionWebhookProcessor:
    return PipelineRunActionWebhookProcessor(event)


def test_processor_type_is_action(
    processor: PipelineRunActionWebhookProcessor,
) -> None:
    assert processor.get_processor_type() == WebhookProcessorType.ACTION


@pytest.mark.asyncio
async def test_should_process_event_valid(
    processor: PipelineRunActionWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="t",
        payload={
            "publisherId": PIPELINES_PUBLISHER_ID,
            "eventType": PipelineRunEvents.PIPELINE_RUN_STATE_CHANGED,
        },
        headers={},
    )
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_wrong_publisher(
    processor: PipelineRunActionWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="t",
        payload={
            "publisherId": "other",
            "eventType": PipelineRunEvents.PIPELINE_RUN_STATE_CHANGED,
        },
        headers={},
    )
    assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_validate_payload_missing_run_id(
    processor: PipelineRunActionWebhookProcessor,
) -> None:
    payload = _payload()
    del payload["resource"]["run"]["id"]
    assert await processor.validate_payload(payload) is False


@pytest.mark.asyncio
async def test_handle_event_reports_success(
    processor: PipelineRunActionWebhookProcessor, monkeypatch: pytest.MonkeyPatch
) -> None:
    port_run = MagicMock()
    port_run.id = "port-run-1"
    port_run.execution_properties = {"reportPipelineStatus": True}
    mock_ocean = _mock_ocean(monkeypatch, port_run=port_run)

    results = await processor._handle_webhook_event(_payload(), MagicMock())

    mock_ocean.port_client.find_run_by_external_id.assert_awaited_once_with(
        "ado_proj-guid_12_4567"
    )
    completed_call = mock_ocean.port_client.report_run_completed.await_args
    assert completed_call.args[0] is port_run
    assert completed_call.args[1] is True
    assert results.updated_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_reports_failure(
    processor: PipelineRunActionWebhookProcessor, monkeypatch: pytest.MonkeyPatch
) -> None:
    port_run = MagicMock()
    port_run.execution_properties = {"reportPipelineStatus": True}
    mock_ocean = _mock_ocean(monkeypatch, port_run=port_run)

    await processor._handle_webhook_event(_payload(result="failed"), MagicMock())

    assert mock_ocean.port_client.report_run_completed.await_args.args[1] is False


@pytest.mark.asyncio
async def test_handle_event_skips_when_not_completed(
    processor: PipelineRunActionWebhookProcessor, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_ocean = _mock_ocean(monkeypatch, port_run=MagicMock())

    await processor._handle_webhook_event(
        _payload(state="inProgress", result=""), MagicMock()
    )

    mock_ocean.port_client.find_run_by_external_id.assert_not_awaited()
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_event_skips_when_status_reporting_disabled(
    processor: PipelineRunActionWebhookProcessor, monkeypatch: pytest.MonkeyPatch
) -> None:
    port_run = MagicMock()
    port_run.execution_properties = {"reportPipelineStatus": False}
    mock_ocean = _mock_ocean(monkeypatch, port_run=port_run)

    await processor._handle_webhook_event(_payload(), MagicMock())

    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_event_reports_when_status_flag_missing(
    processor: PipelineRunActionWebhookProcessor, monkeypatch: pytest.MonkeyPatch
) -> None:
    port_run = MagicMock()
    port_run.execution_properties = {}
    mock_ocean = _mock_ocean(monkeypatch, port_run=port_run)

    await processor._handle_webhook_event(_payload(), MagicMock())

    assert mock_ocean.port_client.report_run_completed.await_args.args[1] is True
