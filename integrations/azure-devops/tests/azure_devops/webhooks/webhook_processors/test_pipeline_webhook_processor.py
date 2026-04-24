import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.webhooks.webhook_processors.pipeline_webhook_processor import (
    PipelineWebhookProcessor,
)
from azure_devops.webhooks.events import PipelineEvents
from azure_devops.client.azure_devops_client import PIPELINES_PUBLISHER_ID


@pytest.fixture
def pipeline_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> PipelineWebhookProcessor:
    mock_client = MagicMock()
    mock_client.get_pipeline = AsyncMock()
    mock_client.enrich_pipelines_with_repository = AsyncMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return PipelineWebhookProcessor(event)


@pytest.mark.asyncio
async def test_pipeline_should_process_event_valid(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": PipelineEvents.PIPELINE_UPDATED,
            "publisherId": PIPELINES_PUBLISHER_ID,
        },
        headers={},
    )
    assert await pipeline_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_pipeline_should_process_event_invalid_publisher(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": PipelineEvents.PIPELINE_UPDATED,
            "publisherId": "wrong-publisher",
        },
        headers={},
    )
    assert await pipeline_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_pipeline_get_matching_kinds(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await pipeline_processor.get_matching_kinds(event)
    assert kinds == ["pipeline"]


@pytest.mark.asyncio
async def test_pipeline_validate_payload_valid(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": PipelineEvents.PIPELINE_UPDATED,
        "publisherId": PIPELINES_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {"checkConfigurationId": "pipeline-123"},
    }
    assert await pipeline_processor.validate_payload(valid_payload) is True


@pytest.mark.asyncio
async def test_pipeline_validate_payload_invalid(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "eventType": PipelineEvents.PIPELINE_UPDATED,
        "publisherId": PIPELINES_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {},
    }
    assert await pipeline_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_pipeline_handle_event_success_no_enrich(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_pipeline = AsyncMock(return_value={"id": "pipeline-123"})
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {"checkConfigurationId": "pipeline-123"},
    }
    resource_config = MagicMock()
    resource_config.selector.include_repo = False

    result = await pipeline_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == "pipeline-123"
    mock_client.get_pipeline.assert_called_once_with("project-123", "pipeline-123")


@pytest.mark.asyncio
async def test_pipeline_handle_event_success_with_enrich(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    pipeline_data = {"id": "pipeline-123"}
    mock_client.get_pipeline = AsyncMock(return_value=pipeline_data)
    mock_client.enrich_pipelines_with_repository = AsyncMock(
        return_value=[{**pipeline_data, "__repository": {}}]
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {"checkConfigurationId": "pipeline-123"},
    }
    resource_config = MagicMock()
    resource_config.selector.include_repo = True

    result = await pipeline_processor.handle_event(payload, resource_config)

    assert len(result.updated_raw_results) == 1
    assert "__repository" in result.updated_raw_results[0]
    mock_client.enrich_pipelines_with_repository.assert_called_once_with(
        [pipeline_data]
    )


@pytest.mark.asyncio
async def test_pipeline_handle_event_not_found(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_pipeline = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {"checkConfigurationId": "pipeline-123"},
    }
    result = await pipeline_processor.handle_event(payload, MagicMock())

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
