import pytest
from unittest.mock import MagicMock, patch
from typing import Any
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from bitbucket_cloud.helpers.utils import ObjectKind
from bitbucket_cloud.webhook_processors.webhook_client import BitbucketWebhookClient

# Patch the module before importing the class
with patch("initialize_client.init_webhook_client") as mock_init_client:
    from bitbucket_cloud.webhook_processors.processors.repository_webhook_processor import (
        RepositoryWebhookProcessor,
    )


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def repository_webhook_processor(
    webhook_client_mock: BitbucketWebhookClient, event: WebhookEvent
) -> RepositoryWebhookProcessor:
    """Create a RepositoryWebhookProcessor with mocked webhook client."""
    repository_webhook_processor = RepositoryWebhookProcessor(event)
    repository_webhook_processor._webhook_client = webhook_client_mock
    return repository_webhook_processor


class TestRepositoryWebhookProcessor:

    @pytest.mark.parametrize(
        "event_key, expected",
        [
            ("repo:created", True),
            ("repo:updated", True),
            ("repo:push", True),
            ("pullrequest:created", False),
            ("pullrequest:updated", False),
            ("invalid:event", False),
        ],
    )
    @pytest.mark.asyncio
    async def test_should_process_event(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        event_key: str,
        expected: bool,
    ) -> None:
        """Test that should_process_event correctly identifies valid repository events."""
        event = WebhookEvent(
            trace_id="test-trace-id", headers={"x-event-key": event_key}, payload={}
        )
        result = await repository_webhook_processor._should_process_event(event)
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_matching_kinds(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        """Test that get_matching_kinds returns the REPOSITORY kind."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-event-key": "repo:created"},
            payload={},
        )
        result = await repository_webhook_processor.get_matching_kinds(event)
        assert result == [ObjectKind.REPOSITORY]

    @pytest.mark.asyncio
    async def test_handle_event(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        webhook_client_mock: MagicMock,
    ) -> None:
        """Test handling a repository event."""
        # Arrange
        payload = {"repository": {"uuid": "repo-123"}}
        resource_config = MagicMock()

        webhook_client_mock.get_repository.return_value = {
            "uuid": "repo-123",
            "name": "Test Repository",
            "description": "This is a test repository",
        }

        # Act
        result = await repository_webhook_processor.handle_event(
            payload, resource_config
        )

        # Assert
        webhook_client_mock.get_repository.assert_called_once_with("repo-123")
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == {
            "uuid": "repo-123",
            "name": "Test Repository",
            "description": "This is a test repository",
        }
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.parametrize(
        "payload, expected",
        [
            ({"repository": {}}, True),
            ({}, False),
            ({"pullrequest": {}}, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_validate_payload(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        payload: dict[str, Any],
        expected: bool,
    ) -> None:
        """Test payload validation with various input scenarios."""
        result = await repository_webhook_processor.validate_payload(payload)
        assert result == expected
