import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.webhooks.webhook_processors.release_webhook_processor import (
    ReleaseWebhookProcessor,
)
from azure_devops.webhooks.events import ReleaseEvents
from azure_devops.client.azure_devops_client import RELEASE_PUBLISHER_ID


@pytest.fixture
def release_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> ReleaseWebhookProcessor:
    mock_client = MagicMock()
    mock_client.get_release = AsyncMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.release_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return ReleaseWebhookProcessor(event)


@pytest.mark.asyncio
async def test_release_get_matching_kinds(
    release_processor: ReleaseWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await release_processor.get_matching_kinds(event)
    assert kinds == ["release"]


@pytest.mark.asyncio
async def test_release_should_process_event_valid(
    release_processor: ReleaseWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": ReleaseEvents.RELEASE_CREATED,
            "publisherId": RELEASE_PUBLISHER_ID,
        },
        headers={},
    )
    assert await release_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_release_should_process_event_abandoned(
    release_processor: ReleaseWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": ReleaseEvents.RELEASE_ABANDONED,
            "publisherId": RELEASE_PUBLISHER_ID,
        },
        headers={},
    )
    assert await release_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_release_should_process_event_invalid_publisher(
    release_processor: ReleaseWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": ReleaseEvents.RELEASE_CREATED,
            "publisherId": "wrong-publisher",
        },
        headers={},
    )
    assert await release_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_release_should_process_event_invalid_type(
    release_processor: ReleaseWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "invalid.event",
            "publisherId": RELEASE_PUBLISHER_ID,
        },
        headers={},
    )
    assert await release_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_release_validate_payload_valid(
    release_processor: ReleaseWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": ReleaseEvents.RELEASE_CREATED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {"release": {"id": 42}},
    }
    assert await release_processor.validate_payload(valid_payload) is True


@pytest.mark.asyncio
async def test_release_validate_payload_missing_project(
    release_processor: ReleaseWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "eventType": ReleaseEvents.RELEASE_CREATED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {},
        "resource": {"release": {"id": 42}},
    }
    assert await release_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_release_validate_payload_missing_release(
    release_processor: ReleaseWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "eventType": ReleaseEvents.RELEASE_CREATED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {},
    }
    assert await release_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_release_handle_event_success(
    release_processor: ReleaseWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_release = AsyncMock(
        return_value={"id": 42, "name": "Release-1", "status": "active"}
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.release_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {"release": {"id": 42}},
    }

    result = await release_processor.handle_event(payload, MagicMock())

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == 42
    assert len(result.deleted_raw_results) == 0
    mock_client.get_release.assert_called_once_with("project-123", 42)


@pytest.mark.asyncio
async def test_release_handle_event_not_found(
    release_processor: ReleaseWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_release = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.release_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {"release": {"id": 42}},
    }

    result = await release_processor.handle_event(payload, MagicMock())

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
