import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from integration import ObjectKind, WorkflowResourceConfig
from webhook_processors.workflow_webhook_processor import WorkflowWebhookProcessor


@pytest.fixture
def mock_event():
    with patch("webhook_processors.workflow_webhook_processor.event") as mock:
        mock.resource_config = MagicMock(spec=WorkflowResourceConfig)
        mock.resource_config.selector.organizations = ["org1"]
        mock.resource_config.selector.state = "all"
        yield mock


@pytest.fixture
def mock_client():
    with patch("webhook_processors.workflow_webhook_processor.get_client") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


@pytest.fixture
def workflow_webhook_processor(mock_event):
    return WorkflowWebhookProcessor(event=mock_event)


@pytest.mark.asyncio
async def test_should_process_event(workflow_webhook_processor):
    # Test valid actions
    for action in ["created", "deleted", "updated", "disabled", "enabled"]:
        assert await workflow_webhook_processor.should_process_event(action, {}) is True

    # Test invalid action
    assert await workflow_webhook_processor.should_process_event("invalid", {}) is False


@pytest.mark.asyncio
async def test_get_matching_kinds(workflow_webhook_processor):
    kinds = await workflow_webhook_processor.get_matching_kinds()
    assert kinds == [ObjectKind.WORKFLOW]


@pytest.mark.asyncio
async def test_validate_payload(workflow_webhook_processor):
    # Test valid payload
    valid_payload = {
        "workflow": {
            "id": 123,
            "name": "test-workflow",
            "path": ".github/workflows/test.yml",
            "state": "active",
        },
        "repository": {
            "name": "test-repo",
            "full_name": "org1/test-repo",
            "owner": {"login": "org1"},
        },
    }
    assert await workflow_webhook_processor.validate_payload(valid_payload) is True

    # Test invalid payloads
    assert await workflow_webhook_processor.validate_payload({}) is False
    assert await workflow_webhook_processor.validate_payload({"workflow": {}}) is False
    assert (
        await workflow_webhook_processor.validate_payload({"repository": {}}) is False
    )


@pytest.mark.asyncio
async def test_handle_event_deleted(workflow_webhook_processor, mock_client):
    payload = {
        "action": "deleted",
        "workflow": {
            "id": 123,
            "name": "test-workflow",
            "path": ".github/workflows/test.yml",
        },
        "repository": {
            "name": "test-repo",
            "full_name": "org1/test-repo",
            "owner": {"login": "org1"},
        },
    }

    result = await workflow_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "123"
    assert result.state == "deleted"


@pytest.mark.asyncio
async def test_handle_event_updated(workflow_webhook_processor, mock_client):
    payload = {
        "action": "created",
        "workflow": {
            "id": 123,
            "name": "test-workflow",
            "path": ".github/workflows/test.yml",
            "state": "active",
            "html_url": "https://github.com/org1/test-repo/blob/main/.github/workflows/test.yml",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
        },
        "repository": {
            "name": "test-repo",
            "full_name": "org1/test-repo",
            "owner": {"login": "org1"},
        },
    }

    mock_client.get_single_resource.return_value = payload["workflow"]

    result = await workflow_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "123"
    assert result.title == "test-workflow"
    assert result.state == "active"
    assert result.repository == "org1/test-repo"


@pytest.mark.asyncio
async def test_handle_event_organization_filter(
    workflow_webhook_processor, mock_client
):
    payload = {
        "action": "created",
        "workflow": {
            "id": 123,
            "name": "test-workflow",
            "path": ".github/workflows/test.yml",
        },
        "repository": {
            "name": "test-repo",
            "full_name": "other-org/test-repo",
            "owner": {"login": "other-org"},
        },
    }

    result = await workflow_webhook_processor.handle_event(payload)
    assert result is None


@pytest.mark.asyncio
async def test_handle_event_state_filter(workflow_webhook_processor, mock_client):
    payload = {
        "action": "created",
        "workflow": {
            "id": 123,
            "name": "test-workflow",
            "path": ".github/workflows/test.yml",
            "state": "disabled",
        },
        "repository": {
            "name": "test-repo",
            "full_name": "org1/test-repo",
            "owner": {"login": "org1"},
        },
    }

    mock_client.get_single_resource.return_value = payload["workflow"]
    workflow_webhook_processor.event.resource_config.selector.state = "active"

    result = await workflow_webhook_processor.handle_event(payload)
    assert result is None


@pytest.mark.asyncio
async def test_handle_event_disabled_enabled(workflow_webhook_processor, mock_client):
    # Test disabled action
    payload = {
        "action": "disabled",
        "workflow": {
            "id": 123,
            "name": "test-workflow",
            "path": ".github/workflows/test.yml",
            "state": "disabled",
        },
        "repository": {
            "name": "test-repo",
            "full_name": "org1/test-repo",
            "owner": {"login": "org1"},
        },
    }

    mock_client.get_single_resource.return_value = payload["workflow"]

    result = await workflow_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "123"
    assert result.state == "disabled"

    # Test enabled action
    payload["action"] = "enabled"
    payload["workflow"]["state"] = "active"
    mock_client.get_single_resource.return_value = payload["workflow"]

    result = await workflow_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "123"
    assert result.state == "active"
