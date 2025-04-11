import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, List, Dict, Tuple
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from bitbucket_cloud.helpers.utils import ObjectKind

# Patch the module before importing the class
with patch("initialize_client.init_webhook_client") as mock_init_client:
    from bitbucket_cloud.webhook_processors.webhook_client import BitbucketWebhookClient
    from bitbucket_cloud.webhook_processors.processors.file_webhook_processor import (
        FileWebhookProcessor,
    )


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def file_webhook_processor(
    webhook_client_mock: BitbucketWebhookClient, event: WebhookEvent
) -> FileWebhookProcessor:
    """Create a FileWebhookProcessor with mocked webhook client."""
    file_webhook_processor = FileWebhookProcessor(event)
    file_webhook_processor._webhook_client = webhook_client_mock
    return file_webhook_processor


class TestFileWebhookProcessor:

    @pytest.mark.parametrize(
        "event_key, expected",
        [
            ("repo:push", True),
            ("repo:created", False),
            ("repo:updated", False),
            ("repo:deleted", False),
            ("invalid:event", False),
        ],
    )
    @pytest.mark.asyncio
    async def test_should_process_event(
        self,
        file_webhook_processor: FileWebhookProcessor,
        event_key: str,
        expected: bool,
    ) -> None:
        """Test that should_process_event correctly identifies valid file events."""
        event = WebhookEvent(
            trace_id="test-trace-id", headers={"x-event-key": event_key}, payload={}
        )
        result = await file_webhook_processor._should_process_event(event)
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_matching_kinds(
        self, file_webhook_processor: FileWebhookProcessor
    ) -> None:
        """Test that get_matching_kinds returns the FILE kind."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-event-key": "repo:push"},
            payload={},
        )
        result = await file_webhook_processor.get_matching_kinds(event)
        assert result == [ObjectKind.FILE]

    @pytest.mark.asyncio
    async def test_handle_event(self) -> None:
        """Test the handle_event function."""
        # Mock the webhook client
        mock_webhook_client = AsyncMock()

        # Mock the process_file_changes function
        mock_updated_results: List[Dict[str, Any]] = [
            {"id": "file1", "content": "content1"}
        ]
        mock_deleted_results: List[Dict[str, Any]] = [{"id": "file2"}]

        async def mock_process_file_changes(
            *args: Any, **kwargs: Any
        ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
            return mock_updated_results, mock_deleted_results

        with patch(
            "bitbucket_cloud.webhook_processors.processors.file_webhook_processor.process_file_changes",
            side_effect=mock_process_file_changes,
        ):
            # Create a processor instance with the required event parameter
            test_event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
            processor = FileWebhookProcessor(event=test_event)
            processor._webhook_client = mock_webhook_client

            # Test payload
            test_payload: Dict[str, Any] = {
                "repository": {"uuid": "repo-123", "name": "test-repo"},
                "push": {"changes": [{"new": {"hash": "new-hash"}}]},
            }

            # Test resource config
            mock_resource_config = MagicMock()
            mock_resource_config.selector.files.skip_parsing = False
            # Set up the tracked_repository field to include our test repository
            mock_resource_config.selector.files.repos = ["test-repo"]

            # Call the handle_event function
            result = await processor.handle_event(test_payload, mock_resource_config)

            # Verify the result
            assert result.updated_raw_results == mock_updated_results
            assert result.deleted_raw_results == mock_deleted_results

    @pytest.mark.parametrize(
        "payload, expected",
        [
            ({"repository": {}, "push": {}}, True),
            ({"repository": {}}, False),
            ({"push": {}}, False),
            ({}, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_validate_payload(
        self,
        file_webhook_processor: FileWebhookProcessor,
        payload: dict[str, Any],
        expected: bool,
    ) -> None:
        """Test payload validation with various input scenarios."""
        result = await file_webhook_processor.validate_payload(payload)
        assert result == expected
