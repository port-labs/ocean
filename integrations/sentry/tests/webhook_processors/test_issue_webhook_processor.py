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

    async def test_handle_sentry_event_success(self) -> None:
        """Test handling of Sentry service hook events with active issue."""
        event = WebhookEvent(trace_id="t8", payload={}, headers={})
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
        event = WebhookEvent(trace_id="t9", payload={}, headers={})
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

    async def test_handle_event_created_action(self) -> None:
        """Issue created events should add to updated_raw_results."""
        event = WebhookEvent(trace_id="t3", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "created",
            "data": {
                "issue": {"id": "12345", "title": "Test Issue", "status": "unresolved"}
            },
            "installation": {"uuid": "test-uuid"},
        }

        result = await processor.handle_event(payload, _resource_config())

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["id"] == "12345"
        assert result.deleted_raw_results == []

    async def test_handle_event_resolved_action(self) -> None:
        """Issue resolved events should add to updated_raw_results."""
        event = WebhookEvent(trace_id="t4", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "resolved",
            "data": {
                "issue": {"id": "12345", "title": "Test Issue", "status": "resolved"}
            },
            "installation": {"uuid": "test-uuid"},
        }

        result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["status"] == "resolved"
        assert result.deleted_raw_results == []

    async def test_handle_event_archived_action(self) -> None:
        """Issue archived events should add to deleted_raw_results."""
        event = WebhookEvent(trace_id="t5", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "archived",
            "data": {"issue": {"id": "12345", "title": "Test Issue"}},
            "installation": {"uuid": "test-uuid"},
        }

        result = await processor.handle_event(payload, _resource_config())

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["id"] == "12345"

    async def test_handle_event_assigned_action(self) -> None:
        """Issue assigned events should add to updated_raw_results."""
        event = WebhookEvent(trace_id="t6", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "assigned",
            "data": {
                "issue": {
                    "id": "12345",
                    "title": "Test Issue",
                    "assignedTo": {"email": "user@example.com"},
                }
            },
            "installation": {"uuid": "test-uuid"},
        }

        result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 1
        assert result.deleted_raw_results == []

    async def test_handle_event_unresolved_action(self) -> None:
        """Issue unresolved events should add to updated_raw_results."""
        event = WebhookEvent(trace_id="t7", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "unresolved",
            "data": {
                "issue": {"id": "12345", "title": "Test Issue", "status": "unresolved"}
            },
            "installation": {"uuid": "test-uuid"},
        }

        result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 1
        assert result.deleted_raw_results == []

    async def test_handle_event_unknown_action(self) -> None:
        """Unknown actions should be skipped."""
        event = WebhookEvent(trace_id="t9", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "unknown_action",
            "data": {"issue": {"id": "12345", "title": "Test Issue"}},
            "installation": {"uuid": "test-uuid"},
        }

        result = await processor.handle_event(payload, _resource_config())

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_get_matching_kinds(self) -> None:
        """Should return ['issue'] for matching kinds."""
        event = WebhookEvent(trace_id="t10", payload={}, headers={})
        processor = SentryIssueWebhookProcessor(event)

        kinds = await processor.get_matching_kinds(event)
        assert kinds == ["issue"]
