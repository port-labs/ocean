import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults
from integration import ObjectKind, RepositoryResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor


@pytest.fixture
def mock_event():
    return WebhookEvent(
        headers={"x-github-event": "repository"},
        payload={
            "action": "created",
            "repository": {
                "id": "123",
                "name": "test-repo",
                "full_name": "test-org/test-repo",
                "private": False,
                "owner": {
                    "login": "test-org"
                }
            }
        },
        trace_id="test-trace-id"
    )


@pytest.fixture
def repository_processor(mock_event):
    return RepositoryWebhookProcessor(event=mock_event)


@pytest.fixture
def mock_resource_config():
    config = MagicMock(spec=RepositoryResourceConfig)
    config.selector = MagicMock()
    config.selector.organizations = ["test-org"]
    config.selector.visibility = "all"
    return config


@pytest.mark.asyncio
async def test_should_process_event_valid(repository_processor, mock_event):
    result = await repository_processor.should_process_event(mock_event)
    assert result is True


@pytest.mark.asyncio
async def test_should_process_event_invalid_event_type(repository_processor):
    event = WebhookEvent(
        headers={"x-github-event": "push"},
        payload={"action": "created"},
        trace_id="test-trace-id"
    )
    result = await repository_processor.should_process_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_should_process_event_invalid_action(repository_processor):
    event = WebhookEvent(
        headers={"x-github-event": "repository"},
        payload={"action": "invalid_action"},
        trace_id="test-trace-id"
    )
    result = await repository_processor.should_process_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_get_matching_kinds(repository_processor, mock_event):
    kinds = await repository_processor.get_matching_kinds(mock_event)
    assert kinds == [ObjectKind.REPOSITORY]


@pytest.mark.asyncio
async def test_authenticate(repository_processor):
    result = await repository_processor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_valid(repository_processor):
    payload = {
        "repository": {"id": "123"},
        "organization": {"login": "test-org"}
    }
    result = await repository_processor.validate_payload(payload)
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_invalid(repository_processor):
    payload = {
        "action": "created"
    }
    result = await repository_processor.validate_payload(payload)
    assert result is False


@pytest.mark.asyncio
async def test_handle_event_created(repository_processor, mock_resource_config):
    mock_client = AsyncMock()
    mock_client.get_single_resource.return_value = {
        "id": "123",
        "name": "test-repo",
        "full_name": "test-org/test-repo",
        "private": False,
        "visibility": "public"
    }
    
    with patch("webhook_processors.repository_webhook_processor.get_client", return_value=mock_client):
        # Create a new event with the correct structure
        event = WebhookEvent(
            headers={"x-github-event": "repository"},
            payload={
                "action": "created",
                "repository": {
                    "id": "123",
                    "name": "test-repo",
                    "full_name": "test-org/test-repo",
                    "private": False,
                    "owner": {
                        "login": "test-org"
                    }
                }
            },
            trace_id="test-trace-id"
        )
        
        result = await repository_processor.handle_event(event, mock_resource_config)
        
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["id"] == "123"


@pytest.mark.asyncio
async def test_handle_event_deleted(repository_processor, mock_resource_config):
    event = WebhookEvent(
        headers={"x-github-event": "repository"},
        payload={
            "action": "deleted",
            "repository": {
                "id": "123",
                "name": "test-repo",
                "full_name": "test-org/test-repo",
                "private": False,
                "owner": {
                    "login": "test-org"
                }
            }
        },
        trace_id="test-trace-id"
    )
    
    result = await repository_processor.handle_event(event, mock_resource_config)
    
    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 1
    assert result.deleted_raw_results[0]["id"] == "123"


@pytest.mark.asyncio
async def test_handle_event_wrong_organization(repository_processor, mock_resource_config):
    # Create a new event with the correct structure
    event = WebhookEvent(
        headers={"x-github-event": "repository"},
        payload={
            "action": "created",
            "repository": {
                "id": "123",
                "name": "test-repo",
                "full_name": "test-org/test-repo",
                "private": False,
                "owner": {
                    "login": "test-org"
                }
            }
        },
        trace_id="test-trace-id"
    )
    
    mock_resource_config.selector.organizations = ["different-org"]
    
    result = await repository_processor.handle_event(event, mock_resource_config)
    
    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
