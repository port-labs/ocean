import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.webhooks.webhook_processors.pipeline_stage_webhook_processor import (
    PipelineStageWebhookProcessor,
)
from azure_devops.webhooks.events import PipelineStageEvents
from azure_devops.client.azure_devops_client import PIPELINES_PUBLISHER_ID


@pytest.fixture
def pipeline_stage_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> PipelineStageWebhookProcessor:
    mock_client = MagicMock()
    mock_client.get_single_project = AsyncMock()
    mock_client.get_pipeline_stage = AsyncMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_stage_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return PipelineStageWebhookProcessor(event)


@pytest.mark.asyncio
async def test_pipeline_stage_should_process_event_valid(
    pipeline_stage_processor: PipelineStageWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": PipelineStageEvents.PIPELINE_STAGE_STATE_CHANGED,
            "publisherId": PIPELINES_PUBLISHER_ID,
        },
        headers={},
    )
    assert await pipeline_stage_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_pipeline_stage_get_matching_kinds(
    pipeline_stage_processor: PipelineStageWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await pipeline_stage_processor.get_matching_kinds(event)
    assert kinds == ["pipeline-stage"]


@pytest.mark.asyncio
async def test_pipeline_stage_validate_payload_valid(
    pipeline_stage_processor: PipelineStageWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": PipelineStageEvents.PIPELINE_STAGE_STATE_CHANGED,
        "publisherId": PIPELINES_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "run": {"id": "run-456"},
            "stage": {"id": "stage-789"},
            "pipeline": {"id": "pipeline-101"},
        },
    }
    assert await pipeline_stage_processor.validate_payload(valid_payload) is True


@pytest.mark.asyncio
async def test_pipeline_stage_handle_event_success(
    pipeline_stage_processor: PipelineStageWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    project = {"id": "project-123"}
    stage = {"id": "stage-789"}
    mock_client.get_single_project = AsyncMock(return_value=project)
    mock_client.get_pipeline_stage = AsyncMock(return_value=stage)
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_stage_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "run": {"id": "run-456"},
            "stage": {"id": "stage-789"},
            "pipeline": {"id": "pipeline-101"},
        },
    }
    result = await pipeline_stage_processor.handle_event(payload, MagicMock())

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == "stage-789"
    mock_client.get_single_project.assert_called_once_with("project-123")
    mock_client.get_pipeline_stage.assert_called_once_with(
        project, "pipeline-101", "run-456", "stage-789"
    )


@pytest.mark.asyncio
async def test_pipeline_stage_handle_event_project_not_found(
    pipeline_stage_processor: PipelineStageWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_single_project = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_stage_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "run": {"id": "run-456"},
            "stage": {"id": "stage-789"},
            "pipeline": {"id": "pipeline-101"},
        },
    }
    result = await pipeline_stage_processor.handle_event(payload, MagicMock())

    assert len(result.updated_raw_results) == 0


@pytest.mark.asyncio
async def test_pipeline_stage_handle_event_stage_not_found(
    pipeline_stage_processor: PipelineStageWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_single_project = AsyncMock(return_value={"id": "project-123"})
    mock_client.get_pipeline_stage = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_stage_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "run": {"id": "run-456"},
            "stage": {"id": "stage-789"},
            "pipeline": {"id": "pipeline-101"},
        },
    }
    result = await pipeline_stage_processor.handle_event(payload, MagicMock())

    assert len(result.updated_raw_results) == 0
