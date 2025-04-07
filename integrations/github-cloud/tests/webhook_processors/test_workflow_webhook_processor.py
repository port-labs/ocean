import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults
from integration import ObjectKind, WorkflowResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.workflow_webhook_processor import WorkflowWebhookProcessor


@pytest.fixture
def workflow_processor(mock_event):
    return WorkflowWebhookProcessor(event=mock_event)


@pytest.fixture
def mock_event():
    return WebhookEvent(
        trace_id="test-trace-id",
        headers={"x-github-event": "workflow_run"},
        payload={
            "action": "created",
            "workflow": {
                "id": "123",
                "name": "test-workflow",
                "state": "active"
            },
            "workflow_run": {
                "id": "456",
                "status": "completed"
            },
            "repository": {
                "name": "test-repo",
                "owner": {
                    "login": "test-org"
                }
            }
        }
    )


@pytest.fixture
def mock_resource_config():
    config = MagicMock(spec=WorkflowResourceConfig)
    config.selector = MagicMock()
    config.selector.organizations = ["test-org"]
    config.selector.state = "all"
    return config


@pytest.mark.asyncio
async def test_should_process_event_valid(workflow_processor, mock_event):
    result = await workflow_processor.should_process_event(mock_event)
    assert result is True


@pytest.mark.asyncio
async def test_should_process_event_invalid_event_type(workflow_processor):
    event = WebhookEvent(
        trace_id="test-trace-id",
        headers={"x-github-event": "push"},
        payload={"action": "created"}
    )
    result = await workflow_processor.should_process_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_should_process_event_invalid_action(workflow_processor):
    event = WebhookEvent(
        trace_id="test-trace-id",
        headers={"x-github-event": "workflow_run"},
        payload={"action": "invalid_action"}
    )
    result = await workflow_processor.should_process_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_get_matching_kinds(workflow_processor):
    kinds = await workflow_processor.get_matching_kinds()
    assert kinds == [ObjectKind.WORKFLOW]


@pytest.mark.asyncio
async def test_authenticate(workflow_processor):
    result = await workflow_processor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_valid(workflow_processor):
    payload = {
        "workflow": {"id": "123"},
        "repository": {"name": "test-repo"}
    }
    result = await workflow_processor.validate_payload(payload)
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_invalid(workflow_processor):
    payload = {
        "workflow": {"id": "123"}
    }
    result = await workflow_processor.validate_payload(payload)
    assert result is False


@pytest.mark.asyncio
async def test_handle_event_created(workflow_processor, mock_event, mock_resource_config):
    mock_client = AsyncMock()
    mock_client.get_single_resource.return_value = {
        "id": "123",
        "name": "test-workflow",
        "state": "active"
    }
    
    with patch("webhook_processors.workflow_webhook_processor.get_client", return_value=mock_client):
        result = await workflow_processor.handle_event(mock_event, mock_resource_config)
        
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["id"] == "123"
        assert result.updated_raw_results[0]["recent_run"] == mock_event.payload["workflow_run"]


@pytest.mark.asyncio
async def test_handle_event_deleted(workflow_processor, mock_event, mock_resource_config):
    # Create a new event with the "deleted" action
    deleted_event = WebhookEvent(
        trace_id="test-trace-id",
        headers={"x-github-event": "workflow_run"},
        payload={
            "action": "deleted",
            "workflow": {
                "id": "123",
                "name": "test-workflow",
                "state": "active"
            },
            "workflow_run": {
                "id": "456",
                "status": "completed"
            },
            "repository": {
                "name": "test-repo",
                "owner": {
                    "login": "test-org"
                }
            }
        }
    )
    
    # Update the processor with the new event
    workflow_processor.event = deleted_event
    
    result = await workflow_processor.handle_event(deleted_event, mock_resource_config)
    
    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 1
    assert result.deleted_raw_results[0]["id"] == "123"


@pytest.mark.asyncio
async def test_handle_event_wrong_organization(workflow_processor, mock_event, mock_resource_config):
    mock_resource_config.selector.organizations = ["different-org"]
    
    result = await workflow_processor.handle_event(mock_event, mock_resource_config)
    
    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_wrong_state(workflow_processor, mock_event, mock_resource_config):
    mock_resource_config.selector.state = "disabled"
    mock_client = AsyncMock()
    mock_client.get_single_resource.return_value = {
        "id": "123",
        "name": "test-workflow",
        "state": "active"
    }
    
    with patch("webhook_processors.workflow_webhook_processor.get_client", return_value=mock_client):
        result = await workflow_processor.handle_event(mock_event, mock_resource_config)
        
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
