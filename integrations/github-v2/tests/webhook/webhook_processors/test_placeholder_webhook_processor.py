import pytest
from unittest.mock import MagicMock

from github.webhook.webhook_processors.placeholder_webhook_processor import (
    PlaceholderWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import Any


@pytest.mark.asyncio
class TestPlaceholderWebhookProcessor:
    """Test the placeholder webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "ping"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> PlaceholderWebhookProcessor:
        """Create a PlaceholderWebhookProcessor instance"""
        return PlaceholderWebhookProcessor(event=mock_event)

    async def test_get_matching_kinds(
        self, processor: PlaceholderWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns REPOSITORY as placeholder"""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.REPOSITORY]

    async def test_handle_event_ping(
        self, processor: PlaceholderWebhookProcessor
    ) -> None:
        """Test handling a ping event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "zen": "Design for failure.",
            "hook_id": 123,
            "hook": {"id": 123},
        }

        result = await processor.handle_event(payload, resource_config)

        assert not result.updated_raw_results
        assert not result.deleted_raw_results

    async def test_handle_event_workflow_run(
        self, processor: PlaceholderWebhookProcessor
    ) -> None:
        """Test handling a workflow_run event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": 123,
                "status": "completed",
                "conclusion": "success",
            },
            "repository": {"id": 456, "full_name": "owner/repo"},
        }

        result = await processor.handle_event(payload, resource_config)

        assert not result.updated_raw_results
        assert not result.deleted_raw_results

    async def test_handle_event_workflow_job(
        self, processor: PlaceholderWebhookProcessor
    ) -> None:
        """Test handling a workflow_job event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "action": "completed",
            "workflow_job": {
                "id": 789,
                "status": "completed",
                "conclusion": "success",
            },
            "repository": {"id": 456, "full_name": "owner/repo"},
        }

        result = await processor.handle_event(payload, resource_config)

        assert not result.updated_raw_results
        assert not result.deleted_raw_results

    async def test_handle_event_push(
        self, processor: PlaceholderWebhookProcessor
    ) -> None:
        """Test handling a push event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "ref": "refs/heads/main",
            "before": "abc123",
            "after": "def456",
            "repository": {"id": 456, "full_name": "owner/repo"},
            "commits": [{"id": "def456", "message": "Test commit"}],
        }

        result = await processor.handle_event(payload, resource_config)

        assert not result.updated_raw_results
        assert not result.deleted_raw_results

    async def test_validate_payload(self, processor: PlaceholderWebhookProcessor) -> None:
        """Test that validate_payload always returns True"""
        assert await processor.validate_payload({}) is True
        assert await processor.validate_payload({"any": "data"}) is True
        assert await processor.validate_payload(None) is True

    async def test_should_process_event(self, processor: PlaceholderWebhookProcessor) -> None:
        """Test should_process_event for all supported events"""
        # Ping event
        ping_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "ping"},
            payload={},
        )
        assert await processor.should_process_event(ping_event) is True

        workflow_run_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "workflow_run"},
            payload={},
        )
        assert await processor.should_process_event(workflow_run_event) is True

        workflow_job_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "workflow_job"},
            payload={},
        )
        assert await processor.should_process_event(workflow_job_event) is True

        # Push event
        push_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "push"},
            payload={},
        )
        assert await processor.should_process_event(push_event) is True


        other_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "issues"},
            payload={},
        )
        assert await processor.should_process_event(other_event) is False
