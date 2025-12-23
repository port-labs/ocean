import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.webhooks.webhook_processors.work_item_webhook_processor import (
    WorkItemWebhookProcessor,
)
from azure_devops.webhooks.events import WorkItemEvents


@pytest.fixture
def work_item_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> WorkItemWebhookProcessor:
    mock_client = MagicMock()
    mock_client.get_work_item = AsyncMock()
    mock_client.get_single_project = AsyncMock(
        return_value={"id": "project-123", "name": "Test Project"}
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.work_item_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return WorkItemWebhookProcessor(event)


@pytest.mark.asyncio
async def test_work_item_should_process_event_created(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": WorkItemEvents.WORK_ITEM_CREATED,
            "publisherId": "tfs",
            "resource": {"id": 123, "project": {"id": "project-123"}},
        },
        headers={},
    )
    assert await work_item_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_work_item_should_process_event_updated(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": WorkItemEvents.WORK_ITEM_UPDATED,
            "publisherId": "tfs",
            "resource": {"id": 123, "project": {"id": "project-123"}},
        },
        headers={},
    )
    assert await work_item_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_work_item_should_process_event_commented(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": WorkItemEvents.WORK_ITEM_COMMENTED,
            "publisherId": "tfs",
            "resource": {"id": 123, "project": {"id": "project-123"}},
        },
        headers={},
    )
    assert await work_item_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_work_item_should_process_event_deleted(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": WorkItemEvents.WORK_ITEM_DELETED,
            "publisherId": "tfs",
            "resource": {"id": 123, "project": {"id": "project-123"}},
        },
        headers={},
    )
    assert await work_item_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_work_item_should_process_event_invalid(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "wrong.event",
            "publisherId": "tfs",
            "resource": {"id": 123},
        },
        headers={},
    )
    assert await work_item_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_work_item_get_matching_kinds(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await work_item_processor.get_matching_kinds(event)
    assert kinds == ["work-item"]


@pytest.mark.asyncio
async def test_work_item_validate_payload_valid(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": WorkItemEvents.WORK_ITEM_CREATED,
        "publisherId": "tfs",
        "resource": {"id": 123, "project": {"id": "project-123"}},
    }
    assert await work_item_processor.validate_payload(valid_payload) is True


@pytest.mark.asyncio
async def test_work_item_validate_payload_missing_id(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "eventType": WorkItemEvents.WORK_ITEM_CREATED,
        "publisherId": "tfs",
        "resource": {"project": {"id": "project-123"}},
    }
    assert await work_item_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_work_item_validate_payload_missing_fields(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {"missing": "fields"}
    assert await work_item_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_work_item_handle_event_created(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_work_item = AsyncMock(
        return_value={
            "id": 123,
            "fields": {"System.Title": "Test Work Item"},
            "url": "https://dev.azure.com/test/workitem/123",
        }
    )
    mock_client.get_single_project = AsyncMock(
        return_value={"id": "project-123", "name": "Test Project"}
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.work_item_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": WorkItemEvents.WORK_ITEM_CREATED,
        "publisherId": "tfs",
        "resource": {"id": 123},
        "resourceContainers": {
            "project": {"id": "project-123", "baseUrl": "https://dev.azure.com/test/"}
        },
    }
    resource_config = MagicMock()

    result = await work_item_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == 123
    assert result.updated_raw_results[0]["__projectId"] == "project-123"
    assert result.updated_raw_results[0]["__project"] == {
        "id": "project-123",
        "name": "Test Project",
    }
    assert len(result.deleted_raw_results) == 0
    mock_client.get_work_item.assert_called_once_with("project-123", 123)
    mock_client.get_single_project.assert_called_once_with("project-123")


@pytest.mark.asyncio
async def test_work_item_handle_event_updated(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_work_item = AsyncMock(
        return_value={
            "id": 456,
            "fields": {"System.Title": "Updated Work Item"},
            "url": "https://dev.azure.com/test/workitem/456",
        }
    )
    mock_client.get_single_project = AsyncMock(
        return_value={"id": "project-456", "name": "Test Project"}
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.work_item_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": WorkItemEvents.WORK_ITEM_UPDATED,
        "publisherId": "tfs",
        "resource": {"id": 456},
        "resourceContainers": {
            "project": {"id": "project-456", "baseUrl": "https://dev.azure.com/test/"}
        },
    }
    resource_config = MagicMock()

    result = await work_item_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == 456
    assert result.updated_raw_results[0]["__projectId"] == "project-456"
    assert result.updated_raw_results[0]["__project"] == {
        "id": "project-456",
        "name": "Test Project",
    }
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_work_item_handle_event_commented(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_work_item = AsyncMock(
        return_value={
            "id": 789,
            "fields": {"System.Title": "Commented Work Item"},
            "url": "https://dev.azure.com/test/workitem/789",
        }
    )
    mock_client.get_single_project = AsyncMock(
        return_value={"id": "project-789", "name": "Test Project"}
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.work_item_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": WorkItemEvents.WORK_ITEM_COMMENTED,
        "publisherId": "tfs",
        "resource": {"id": 789},
        "resourceContainers": {
            "project": {"id": "project-789", "baseUrl": "https://dev.azure.com/test/"}
        },
    }
    resource_config = MagicMock()

    result = await work_item_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == 789
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_work_item_handle_event_deleted(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_single_project = AsyncMock(
        return_value={"id": "project-999", "name": "Test Project"}
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.work_item_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    payload = {
        "eventType": WorkItemEvents.WORK_ITEM_DELETED,
        "publisherId": "tfs",
        "resource": {"id": 999},
        "resourceContainers": {
            "project": {"id": "project-999", "baseUrl": "https://dev.azure.com/test/"}
        },
    }
    resource_config = MagicMock()

    result = await work_item_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 1
    assert result.deleted_raw_results[0]["id"] == 999
    assert "__projectId" not in result.deleted_raw_results[0]
    assert "__project" not in result.deleted_raw_results[0]


@pytest.mark.asyncio
async def test_work_item_handle_event_missing_work_item_id(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    payload = {
        "eventType": WorkItemEvents.WORK_ITEM_CREATED,
        "publisherId": "tfs",
        "resource": {},
        "resourceContainers": {
            "project": {"id": "project-123", "baseUrl": "https://dev.azure.com/test/"}
        },
    }
    resource_config = MagicMock()

    result = await work_item_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_work_item_handle_event_missing_project_id(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
) -> None:
    payload = {
        "eventType": WorkItemEvents.WORK_ITEM_CREATED,
        "publisherId": "tfs",
        "resource": {"id": 123},
        "resourceContainers": {"project": {"id": None}}
    }
    resource_config = MagicMock()

    result = await work_item_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_work_item_handle_event_not_found(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_work_item = AsyncMock(return_value=None)
    mock_client.get_single_project = AsyncMock(
        return_value={"id": "project-404", "name": "Test Project"}
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.work_item_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": WorkItemEvents.WORK_ITEM_UPDATED,
        "publisherId": "tfs",
        "resource": {"id": 404},
        "resourceContainers": {
            "project": {"id": "project-404", "baseUrl": "https://dev.azure.com/test/"}
        },
    }
    resource_config = MagicMock()

    result = await work_item_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_work_item_handle_event_exception(
    work_item_processor: WorkItemWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_work_item = AsyncMock(side_effect=Exception("API Error"))
    mock_client.get_single_project = AsyncMock(
        return_value={"id": "project-500", "name": "Test Project"}
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.work_item_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": WorkItemEvents.WORK_ITEM_CREATED,
        "publisherId": "tfs",
        "resource": {"id": 500},
        "resourceContainers": {
            "project": {"id": "project-500", "baseUrl": "https://dev.azure.com/test/"}
        },
    }
    resource_config = MagicMock()

    result = await work_item_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
