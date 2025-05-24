import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from github_cloud.webhook.webhook_factory import (
    RepositoryWebhookFactory,
    OrganizationWebhookFactory
)
from github_cloud.webhook.events import RepositoryEvents, OrganizationEvents
from github_cloud.clients.github_client import GitHubCloudClient

class AsyncIterator:
    def __init__(self, items):
        self._items = items
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item

@pytest.fixture
def mock_github_client():
    client = MagicMock(spec=GitHubCloudClient)
    client.rest = AsyncMock()
    return client

@pytest.fixture
def app_host():
    return "https://example.com"

@pytest.fixture
def webhook_url():
    return "https://example.com/webhook"

@pytest.fixture
def github_webhook_endpoint():
    return "https://api.github.com/repos/owner/repo/hooks"

@pytest.mark.asyncio
async def test_repository_webhook_factory_create_new(mock_github_client, app_host, webhook_url, github_webhook_endpoint):
    # Setup
    factory = RepositoryWebhookFactory(mock_github_client, app_host)
    def paginated_resource(*args, **kwargs):
        return AsyncIterator([[]])
    mock_github_client.rest.get_paginated_resource = paginated_resource
    mock_github_client.rest.send_api_request.return_value = {
        "id": 123,
        "config": {"url": webhook_url}
    }

    # Execute
    result = await factory.create(webhook_url, github_webhook_endpoint)

    # Verify
    assert result == {"id": 123, "config": {"url": webhook_url}}
    mock_github_client.rest.send_api_request.assert_called_once()
    call_args = mock_github_client.rest.send_api_request.call_args
    args, kwargs = call_args[0], call_args[1]
    assert args[0] == "POST"
    assert args[1] == github_webhook_endpoint
    data = kwargs["data"]
    assert data["name"] == "web"
    assert data["active"] is True
    assert "events" in data
    assert data["config"]["url"] == webhook_url
    assert data["config"]["content_type"] == "json"
    assert data["config"]["insecure_ssl"] == "0"

@pytest.mark.asyncio
async def test_repository_webhook_factory_create_existing(mock_github_client, app_host, webhook_url, github_webhook_endpoint):
    # Setup
    factory = RepositoryWebhookFactory(mock_github_client, app_host)
    def paginated_resource(*args, **kwargs):
        return AsyncIterator([[{"config": {"url": webhook_url}}]])
    mock_github_client.rest.get_paginated_resource = paginated_resource

    # Execute
    result = await factory.create(webhook_url, github_webhook_endpoint)

    # Verify
    assert result == {}
    mock_github_client.rest.send_api_request.assert_not_called()

@pytest.mark.asyncio
async def test_organization_webhook_factory_create_new(mock_github_client, app_host, webhook_url, github_webhook_endpoint):
    # Setup
    factory = OrganizationWebhookFactory(mock_github_client, app_host)
    def paginated_resource(*args, **kwargs):
        return AsyncIterator([[]])
    mock_github_client.rest.get_paginated_resource = paginated_resource
    mock_github_client.rest.send_api_request.return_value = {
        "id": 123,
        "config": {"url": webhook_url}
    }

    # Execute
    result = await factory.create(webhook_url, github_webhook_endpoint)

    # Verify
    assert result == {"id": 123, "config": {"url": webhook_url}}
    mock_github_client.rest.send_api_request.assert_called_once()
    call_args = mock_github_client.rest.send_api_request.call_args
    args, kwargs = call_args[0], call_args[1]
    assert args[0] == "POST"
    assert args[1] == github_webhook_endpoint
    data = kwargs["data"]
    assert data["name"] == "web"
    assert data["active"] is True
    assert "events" in data
    assert data["config"]["url"] == webhook_url
    assert data["config"]["content_type"] == "json"
    assert data["config"]["insecure_ssl"] == "0"

@pytest.mark.asyncio
async def test_organization_webhook_factory_create_existing(mock_github_client, app_host, webhook_url, github_webhook_endpoint):
    # Setup
    factory = OrganizationWebhookFactory(mock_github_client, app_host)
    def paginated_resource(*args, **kwargs):
        return AsyncIterator([[{"config": {"url": webhook_url}}]])
    mock_github_client.rest.get_paginated_resource = paginated_resource

    # Execute
    result = await factory.create(webhook_url, github_webhook_endpoint)

    # Verify
    assert result == {}
    mock_github_client.rest.send_api_request.assert_not_called()

def test_repository_webhook_factory_events():
    factory = RepositoryWebhookFactory(MagicMock(), "https://example.com")
    events = factory.webhook_events()
    assert isinstance(events, RepositoryEvents)
    assert events.push is True
    assert events.pull_request is True
    assert events.issues is True
    assert events.release is True
    assert events.workflow_run is True
    assert events.workflow_job is True
    assert events.member is True

def test_organization_webhook_factory_events():
    factory = OrganizationWebhookFactory(MagicMock(), "https://example.com")
    events = factory.webhook_events()
    assert isinstance(events, OrganizationEvents)
    assert events.member is True
    assert events.membership is True
    assert events.organization is True
    assert events.team is True
    assert events.team_add is True
    assert events.repository is True

@pytest.mark.asyncio
async def test_webhook_factory_invalid_response(mock_github_client, app_host, webhook_url, github_webhook_endpoint):
    # Setup
    factory = RepositoryWebhookFactory(mock_github_client, app_host)
    def paginated_resource(*args, **kwargs):
        return AsyncIterator([[]])
    mock_github_client.rest.get_paginated_resource = paginated_resource
    mock_github_client.rest.send_api_request.return_value = {
        "config": {"url": webhook_url}  # Missing 'id' field
    }

    # Execute and verify
    with pytest.raises(Exception, match="Invalid webhook response"):
        await factory.create(webhook_url, github_webhook_endpoint)
