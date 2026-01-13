import pytest
from unittest.mock import AsyncMock, patch

from webhook_processors.issue_webhook_processor import SentryIssueWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
    Selector,
)
from integration import ObjectKind


def _resource_config() -> ResourceConfig:
    """Create a minimal ResourceConfig for testing."""
    port = PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier=".id",
                title=".title",
                blueprint="sentryIssue",
                properties={},
            )
        )
    )
    return ResourceConfig(kind="issue", selector=Selector(query="true"), port=port)


@pytest.mark.asyncio
class TestSentryIssueWebhookProcessor:
    async def test_should_process_event(self) -> None:
        """Should always return True for issue events as per implementation."""
        event = WebhookEvent(trace_id="t1", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)
        result = await processor._should_process_event(event)
        assert result is True

    async def test_get_matching_kinds(self) -> None:
        """Should return [ObjectKind.ISSUE] for matching kinds."""
        event = WebhookEvent(trace_id="t10", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        kinds = await processor.get_matching_kinds(event)
        assert kinds == [ObjectKind.ISSUE]

    async def test_validate_integration_payload_valid(self) -> None:
        """Payload with group.id and project.slug should be valid."""
        event = WebhookEvent(trace_id="t2", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {"group": {"id": "12345"}, "project": {"slug": "test-project"}}
        result = await processor.validate_payload(payload)
        assert result is True

    async def test_validate_integration_payload_missing_group(self) -> None:
        """Payload without group should be invalid."""
        event = WebhookEvent(trace_id="t3", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {"project": {"slug": "test-project"}}
        result = await processor.validate_payload(payload)
        assert result is False

    async def test_handle_event_without_group_returns_empty(self) -> None:
        """Events without 'group' key should return empty results."""
        event = WebhookEvent(trace_id="t5", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        # Sentry integration platform webhook format (action-based)
        # This format is not processed by the current implementation
        payload = {
            "action": "created",
            "data": {
                "issue": {"id": "12345", "title": "Test Issue", "status": "unresolved"}
            },
            "installation": {"uuid": "test-uuid"},
        }

        result = await processor.handle_event(payload, _resource_config())

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_handle_sentry_event_success(self) -> None:
        """Test handling of Sentry service hook events with active issue."""
        event = WebhookEvent(trace_id="t6", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {"group": {"id": "12345"}, "project": {"slug": "test-project"}}

        mock_client = AsyncMock()
        mock_issue = {"id": "12345", "title": "Test Issue"}
        mock_client.get_issue.return_value = mock_issue

        with patch(
            "webhook_processors.issue_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["id"] == "12345"
        assert result.deleted_raw_results == []
        mock_client.get_issue.assert_called_once_with("12345")

    async def test_handle_sentry_event_deleted(self) -> None:
        """Test handling of Sentry service hook events when issue is not found."""
        event = WebhookEvent(trace_id="t7", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {"group": {"id": "12345"}, "project": {"slug": "test-project"}}

        mock_client = AsyncMock()
        mock_client.get_issue.return_value = None

        with patch(
            "webhook_processors.issue_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, _resource_config())

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["id"] == "12345"

    async def test_handle_sentry_event_with_different_issue_id(self) -> None:
        """Test handling with a different issue ID."""
        event = WebhookEvent(trace_id="t8", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {"group": {"id": "67890"}, "project": {"slug": "another-project"}}

        mock_client = AsyncMock()
        mock_issue = {
            "id": "67890",
            "title": "Another Test Issue",
            "status": "resolved",
        }
        mock_client.get_issue.return_value = mock_issue

        with patch(
            "webhook_processors.issue_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["id"] == "67890"
        assert result.updated_raw_results[0]["title"] == "Another Test Issue"
        assert result.deleted_raw_results == []
        mock_client.get_issue.assert_called_once_with("67890")
