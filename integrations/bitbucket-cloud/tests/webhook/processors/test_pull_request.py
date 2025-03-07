import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from bitbucket_integration.utils import ObjectKind

# Patch the module before importing the class
with patch("initialize_client.init_webhook_client") as mock_init_client:
    mock_client = MagicMock()
    mock_init_client.return_value = mock_client
    from bitbucket_integration.webhook.webhook_client import BitbucketWebhookClient
    from bitbucket_integration.webhook.processors.pull_request import (
        PullRequestWebhookProcessor,
    )


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def webhook_client_mock():
    """Create a mocked webhook client."""
    client = AsyncMock(spec=BitbucketWebhookClient)
    client.get_pull_request = AsyncMock()
    return client


@pytest.fixture
def mock_event_context():
    """Create a mocked event context."""
    context = MagicMock()
    return context


@pytest.fixture
def mock_ocean_context():
    """Create a mocked ocean context."""
    context = MagicMock()
    return context


@pytest.fixture
def pull_request_webhook_processor(mock_ocean_context, webhook_client_mock, event: WebhookEvent):
    """Create a PullRequestWebhookProcessor with mocked webhook client."""
    pull_request_webhook_processor = PullRequestWebhookProcessor(event)
    pull_request_webhook_processor._webhook_client = webhook_client_mock
    return pull_request_webhook_processor


class TestPullRequestWebhookProcessor:

    @pytest.mark.parametrize(
        "event_key, expected",
        [
            ("pullrequest:created", True),
            ("pullrequest:updated", True),
            ("pullrequest:approved", True),
            ("pullrequest:unapproved", True),
            ("pullrequest:fulfilled", True),
            ("pullrequest:rejected", True),
            ("repo:created", False),
            ("repo:updated", False),
            ("repo:deleted", False),
            ("invalid:event", False),
        ],
    )
    @pytest.mark.asyncio
    async def test_should_process_event(self, pull_request_webhook_processor, event_key, expected, mock_event_context):
        """Test that should_process_event correctly identifies valid PR events."""
        event = WebhookEvent(
            trace_id="test-trace-id", headers={"x-event-key": event_key}, payload={}
        )
        result = await pull_request_webhook_processor.should_process_event(event)
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_matching_kinds(self, pull_request_webhook_processor, mock_event_context):
        """Test that get_matching_kinds returns the PULL_REQUEST kind."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-event-key": "pullrequest:created"},
            payload={},
        )
        result = await pull_request_webhook_processor.get_matching_kinds(event)
        assert result == [ObjectKind.PULL_REQUEST]

    @pytest.mark.asyncio
    async def test_handle_event(self, pull_request_webhook_processor, webhook_client_mock, mock_event_context):
        """Test handling a pull request event."""
        # Arrange
        payload = {"repository": {"uuid": "repo-123"}, "pullrequest": {"id": "pr-456"}}
        resource_config = MagicMock()

        webhook_client_mock.get_pull_request.return_value = {
            "id": "pr-456",
            "title": "Test PR",
            "description": "This is a test pull request",
        }

        # Act
        result = await pull_request_webhook_processor.handle_event(payload, resource_config)

        # Assert
        webhook_client_mock.get_pull_request.assert_called_once_with(
            "repo-123", "pr-456"
        )
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == {
            "id": "pr-456",
            "title": "Test PR",
            "description": "This is a test pull request",
        }
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.parametrize(
        "payload, expected",
        [
            ({"repository": {}, "pullrequest": {}}, True),
            ({"repository": {}}, False),
            ({"pullrequest": {}}, False),
            ({}, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_validate_payload(self, pull_request_webhook_processor, payload, expected, mock_event_context, mock_ocean_context):
        """Test payload validation with various input scenarios."""
        result = await pull_request_webhook_processor.validate_payload(payload)
        assert result == expected
