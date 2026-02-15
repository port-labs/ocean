import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.webhooks.webhook_processors.pipeline_run_webhook_processor import (
    PipelineRunWebhookProcessor,
)
from azure_devops.webhooks.events import PipelineRunEvents
from azure_devops.client.azure_devops_client import PIPELINES_PUBLISHER_ID


@pytest.fixture
def pipeline_run_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> PipelineRunWebhookProcessor:
    mock_client = MagicMock()
    mock_client.get_pipeline_run = AsyncMock()
    mock_client.get_single_project = AsyncMock()
    mock_client.get_pipeline = AsyncMock()
    mock_client.annotate_runs = MagicMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_run_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return PipelineRunWebhookProcessor(event)


@pytest.mark.asyncio
async def test_pipeline_run_should_process_event_valid(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": PipelineRunEvents.PIPELINE_RUN_STATE_CHANGED,
            "publisherId": PIPELINES_PUBLISHER_ID,
        },
        headers={},
    )
    assert await pipeline_run_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_pipeline_run_should_process_event_invalid_publisher(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": PipelineRunEvents.PIPELINE_RUN_STATE_CHANGED,
            "publisherId": "wrong-publisher",
        },
        headers={},
    )
    assert await pipeline_run_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_pipeline_run_should_process_event_invalid_type(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "invalid.event",
            "publisherId": PIPELINES_PUBLISHER_ID,
        },
        headers={},
    )
    assert await pipeline_run_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_pipeline_run_get_matching_kinds(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await pipeline_run_processor.get_matching_kinds(event)
    assert kinds == ["pipeline-run"]


@pytest.mark.asyncio
async def test_pipeline_run_validate_payload_valid(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": PipelineRunEvents.PIPELINE_RUN_STATE_CHANGED,
        "publisherId": PIPELINES_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "run": {"id": "run-456"},
            "pipeline": {"id": "pipeline-789"},
        },
    }
    assert await pipeline_run_processor.validate_payload(valid_payload) is True


@pytest.mark.asyncio
async def test_pipeline_run_validate_payload_missing_project(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "resourceContainers": {},
        "resource": {
            "run": {"id": "run-456"},
            "pipeline": {"id": "pipeline-789"},
        },
    }
    assert await pipeline_run_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_pipeline_run_validate_payload_missing_run(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "pipeline": {"id": "pipeline-789"},
        },
    }
    assert await pipeline_run_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_pipeline_run_validate_payload_missing_pipeline(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "run": {"id": "run-456"},
        },
    }
    assert await pipeline_run_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_pipeline_run_handle_event_success(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_pipeline_run = AsyncMock(return_value={"id": "run-456"})
    mock_client.get_single_project = AsyncMock(return_value={"id": "project-123"})
    mock_client.get_pipeline = AsyncMock(return_value={"id": "pipeline-789"})
    mock_client.annotate_runs = MagicMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_run_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "run": {"id": "run-456"},
            "pipeline": {"id": "pipeline-789"},
        },
    }
    resource_config = MagicMock()

    result = await pipeline_run_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == "run-456"
    assert len(result.deleted_raw_results) == 0
    mock_client.get_pipeline_run.assert_called_once_with(
        "project-123", "pipeline-789", "run-456"
    )
    mock_client.get_single_project.assert_called_once_with("project-123")
    mock_client.get_pipeline.assert_called_once_with("project-123", "pipeline-789")
    mock_client.annotate_runs.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_run_handle_event_not_found(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_pipeline_run = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_run_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "run": {"id": "run-456"},
            "pipeline": {"id": "pipeline-789"},
        },
    }
    result = await pipeline_run_processor.handle_event(payload, MagicMock())

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_pipeline_run_handle_event_project_not_found(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_pipeline_run = AsyncMock(return_value={"id": "run-456"})
    mock_client.get_single_project = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_run_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "run": {"id": "run-456"},
            "pipeline": {"id": "pipeline-789"},
        },
    }
    result = await pipeline_run_processor.handle_event(payload, MagicMock())

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_pipeline_run_handle_event_pipeline_not_found(
    pipeline_run_processor: PipelineRunWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_pipeline_run = AsyncMock(return_value={"id": "run-456"})
    mock_client.get_single_project = AsyncMock(return_value={"id": "project-123"})
    mock_client.get_pipeline = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_run_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "run": {"id": "run-456"},
            "pipeline": {"id": "pipeline-789"},
        },
    }
    result = await pipeline_run_processor.handle_event(payload, MagicMock())

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
