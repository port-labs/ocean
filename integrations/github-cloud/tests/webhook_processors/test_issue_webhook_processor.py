import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults
from integration import ObjectKind, IssueResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor


@pytest.fixture
def mock_event():
    return WebhookEvent(
        headers={"x-github-event": "issues"},
        payload={
            "action": "opened",
            "issue": {
                "id": "123",
                "number": 1,
                "title": "Test Issue",
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
def issue_processor(mock_event):
    return IssueWebhookProcessor(event=mock_event)


@pytest.fixture
def mock_resource_config():
    config = MagicMock(spec=IssueResourceConfig)
    config.selector = MagicMock()
    config.selector.organizations = ["test-org"]
    config.selector.state = "all"
    return config


@pytest.mark.asyncio
async def test_should_process_event_valid(issue_processor, mock_event):
    result = await issue_processor.should_process_event(mock_event)
    assert result is True


@pytest.mark.asyncio
async def test_should_process_event_invalid_event_type(issue_processor):
    event = WebhookEvent(
        headers={"x-github-event": "push"},
        payload={"action": "opened"},
        trace_id="test-trace-id"
    )
    result = await issue_processor.should_process_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_should_process_event_invalid_action(issue_processor):
    event = WebhookEvent(
        headers={"x-github-event": "issues"},
        payload={"action": "invalid_action"},
        trace_id="test-trace-id"
    )
    result = await issue_processor.should_process_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_get_matching_kinds(issue_processor):
    kinds = await issue_processor.get_matching_kinds()
    assert kinds == [ObjectKind.ISSUE]


@pytest.mark.asyncio
async def test_authenticate(issue_processor):
    result = await issue_processor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_valid(issue_processor):
    payload = {
        "issue": {"id": "123"},
        "repository": {"name": "test-repo"}
    }
    result = await issue_processor.validate_payload(payload)
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_invalid(issue_processor):
    payload = {
        "issue": {"id": "123"}
    }
    result = await issue_processor.validate_payload(payload)
    assert result is False


@pytest.mark.asyncio
async def test_handle_event_created(issue_processor, mock_event, mock_resource_config):
    mock_client = AsyncMock()
    mock_client.get_single_resource.return_value = {
        "id": "123",
        "number": 1,
        "title": "Test Issue",
        "state": "open"
    }
    
    with patch("webhook_processors.issue_webhook_processor.get_client", return_value=mock_client):
        # Create a new event with the correct structure
        event = WebhookEvent(
            headers={"x-github-event": "issues"},
            payload={
                "action": "opened",
                "issue": {
                    "id": "123",
                    "number": 1,
                    "title": "Test Issue",
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
        
        result = await issue_processor.handle_event(event, mock_resource_config)
        
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["id"] == "123"


@pytest.mark.asyncio
async def test_handle_event_deleted(issue_processor, mock_resource_config):
    event = WebhookEvent(
        headers={"x-github-event": "issues"},
        payload={
            "action": "deleted",
            "issue": {
                "id": "123",
                "number": 1,
                "title": "Test Issue",
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
    
    result = await issue_processor.handle_event(event, mock_resource_config)
    
    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 1
    assert result.deleted_raw_results[0]["id"] == "123"


@pytest.mark.asyncio
async def test_handle_event_wrong_organization(issue_processor, mock_resource_config):
    # Create a new event with the correct structure
    event = WebhookEvent(
        headers={"x-github-event": "issues"},
        payload={
            "action": "opened",
            "issue": {
                "id": "123",
                "number": 1,
                "title": "Test Issue",
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
    
    result = await issue_processor.handle_event(event, mock_resource_config)
    
    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
