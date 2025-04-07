import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults
from integration import ObjectKind, TeamResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.team_webhook_processor import TeamWebhookProcessor


@pytest.fixture
def mock_event():
    return WebhookEvent(
        headers={"x-github-event": "team"},
        payload={
            "action": "created",
            "team": {
                "id": "123",
                "name": "test-team",
                "slug": "test-team"
            },
            "organization": {
                "login": "test-org"
            }
        },
        trace_id="test-trace-id"
    )


@pytest.fixture
def team_processor(mock_event):
    return TeamWebhookProcessor(event=mock_event)


@pytest.fixture
def mock_resource_config():
    config = MagicMock(spec=TeamResourceConfig)
    config.selector = MagicMock()
    config.selector.organizations = ["test-org"]
    return config


@pytest.mark.asyncio
async def test_should_process_event_valid(team_processor, mock_event):
    result = await team_processor.should_process_event(mock_event)
    assert result is True


@pytest.mark.asyncio
async def test_should_process_event_invalid_event_type(team_processor):
    event = WebhookEvent(
        headers={"x-github-event": "push"},
        payload={"action": "created"},
        trace_id="test-trace-id"
    )
    result = await team_processor.should_process_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_should_process_event_invalid_action(team_processor):
    event = WebhookEvent(
        headers={"x-github-event": "team"},
        payload={"action": "invalid_action"},
        trace_id="test-trace-id"
    )
    result = await team_processor.should_process_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_get_matching_kinds(team_processor):
    kinds = await team_processor.get_matching_kinds()
    assert kinds == [ObjectKind.TEAM]


@pytest.mark.asyncio
async def test_authenticate(team_processor):
    result = await team_processor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_valid(team_processor):
    payload = {
        "team": {"id": "123"},
        "organization": {"login": "test-org"}
    }
    result = await team_processor.validate_payload(payload)
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_invalid(team_processor):
    payload = {
        "team": {"id": "123"}
    }
    result = await team_processor.validate_payload(payload)
    assert result is False


@pytest.mark.asyncio
async def test_handle_event_created(team_processor, mock_resource_config):
    mock_client = AsyncMock()
    mock_client.get_single_resource.return_value = {
        "id": "123",
        "name": "test-team",
        "slug": "test-team"
    }
    
    with patch("webhook_processors.team_webhook_processor.get_client", return_value=mock_client):
        # Create a new event with the correct structure
        event = WebhookEvent(
            headers={"x-github-event": "team"},
            payload={
                "action": "created",
                "team": {
                    "id": "123",
                    "name": "test-team",
                    "slug": "test-team"
                },
                "organization": {
                    "login": "test-org"
                }
            },
            trace_id="test-trace-id"
        )
        
        result = await team_processor.handle_event(event, mock_resource_config)
        
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["id"] == "123"


@pytest.mark.asyncio
async def test_handle_event_deleted(team_processor, mock_resource_config):
    event = WebhookEvent(
        headers={"x-github-event": "team"},
        payload={
            "action": "deleted",
            "team": {
                "id": "123",
                "name": "test-team",
                "slug": "test-team"
            },
            "organization": {
                "login": "test-org"
            }
        },
        trace_id="test-trace-id"
    )
    
    result = await team_processor.handle_event(event, mock_resource_config)
    
    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 1
    assert result.deleted_raw_results[0]["id"] == "123"


@pytest.mark.asyncio
async def test_handle_event_wrong_organization(team_processor, mock_resource_config):
    # Create a new event with the correct structure
    event = WebhookEvent(
        headers={"x-github-event": "team"},
        payload={
            "action": "created",
            "team": {
                "id": "123",
                "name": "test-team",
                "slug": "test-team"
            },
            "organization": {
                "login": "test-org"
            }
        },
        trace_id="test-trace-id"
    )
    
    mock_resource_config.selector.organizations = ["different-org"]
    
    result = await team_processor.handle_event(event, mock_resource_config)
    
    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
