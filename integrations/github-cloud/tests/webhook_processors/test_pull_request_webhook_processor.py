import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults
from integration import ObjectKind, PullRequestResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.pull_request_webhook_processor import PullRequestWebhookProcessor


@pytest.fixture
def mock_event():
    return WebhookEvent(
        headers={"x-github-event": "pull_request"},
        payload={
            "action": "opened",
            "pull_request": {
                "id": "123",
                "number": 1,
                "title": "Test PR",
                "state": "open"
            },
            "repository": {
                "name": "test-repo",
                "owner": {
                    "login": "test-org"
                }
            }
        },
        trace_id="test-trace-id"
    )


@pytest.fixture
def pull_request_processor(mock_event):
    return PullRequestWebhookProcessor(event=mock_event)


@pytest.fixture
def mock_resource_config():
    config = MagicMock(spec=PullRequestResourceConfig)
    config.selector = MagicMock()
    config.selector.organizations = ["test-org"]
    config.selector.state = "all"
    return config


@pytest.mark.asyncio
async def test_should_process_event_valid(pull_request_processor, mock_event):
    result = await pull_request_processor.should_process_event(mock_event)
    assert result is True


@pytest.mark.asyncio
async def test_should_process_event_invalid_event_type(pull_request_processor):
    event = WebhookEvent(
        headers={"x-github-event": "push"},
        payload={"action": "opened"},
        trace_id="test-trace-id"
    )
    result = await pull_request_processor.should_process_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_should_process_event_invalid_action(pull_request_processor):
    event = WebhookEvent(
        headers={"x-github-event": "pull_request"},
        payload={"action": "invalid_action"},
        trace_id="test-trace-id"
    )
    result = await pull_request_processor.should_process_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_get_matching_kinds(pull_request_processor):
    kinds = await pull_request_processor.get_matching_kinds()
    assert kinds == [ObjectKind.PULL_REQUEST]


@pytest.mark.asyncio
async def test_authenticate(pull_request_processor):
    result = await pull_request_processor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_valid(pull_request_processor):
    payload = {
        "pull_request": {"id": "123"},
        "repository": {"name": "test-repo"}
    }
    result = await pull_request_processor.validate_payload(payload)
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_invalid(pull_request_processor):
    payload = {
        "pull_request": {"id": "123"}
    }
    result = await pull_request_processor.validate_payload(payload)
    assert result is False


@pytest.mark.asyncio
async def test_handle_event_created(pull_request_processor, mock_resource_config):
    mock_client = AsyncMock()
    mock_client.get_single_resource.return_value = {
        "id": "123",
        "number": 1,
        "title": "Test PR",
        "state": "open"
    }
    
    with patch("webhook_processors.pull_request_webhook_processor.get_client", return_value=mock_client):
        # Create a new event with the correct structure
        event = WebhookEvent(
            headers={"x-github-event": "pull_request"},
            payload={
                "action": "opened",
                "pull_request": {
                    "id": "123",
                    "number": 1,
                    "title": "Test PR",
                    "state": "open"
                },
                "repository": {
                    "name": "test-repo",
                    "owner": {
                        "login": "test-org"
                    }
                }
            },
            trace_id="test-trace-id"
        )
        
        result = await pull_request_processor.handle_event(event, mock_resource_config)
        
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["id"] == "123"


@pytest.mark.asyncio
async def test_handle_event_deleted(pull_request_processor, mock_resource_config):
    mock_client = AsyncMock()
    mock_client.get_single_resource.return_value = {
        "id": "123",
        "number": 1,
        "title": "Test PR",
        "state": "open"
    }
    
    with patch("webhook_processors.pull_request_webhook_processor.get_client", return_value=mock_client):
        event = WebhookEvent(
            headers={"x-github-event": "pull_request"},
            payload={
                "action": "closed",
                "pull_request": {
                    "id": "123",
                    "number": 1,
                    "title": "Test PR",
                    "state": "open",
                    "merged": False
                },
                "repository": {
                    "name": "test-repo",
                    "owner": {
                        "login": "test-org"
                    }
                }
            },
            trace_id="test-trace-id"
        )
        
        result = await pull_request_processor.handle_event(event, mock_resource_config)
        
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["id"] == "123"


@pytest.mark.asyncio
async def test_handle_event_wrong_organization(pull_request_processor, mock_resource_config):
    # Create a new event with the correct structure
    event = WebhookEvent(
        headers={"x-github-event": "pull_request"},
        payload={
            "action": "opened",
            "pull_request": {
                "id": "123",
                "number": 1,
                "title": "Test PR",
                "state": "open"
            },
            "repository": {
                "name": "test-repo",
                "owner": {
                    "login": "test-org"
                }
            }
        },
        trace_id="test-trace-id"
    )
    
    mock_resource_config.selector.organizations = ["different-org"]
    
    result = await pull_request_processor.handle_event(event, mock_resource_config)
    
    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
