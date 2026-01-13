import pytest
from unittest.mock import AsyncMock, patch

from webhook_processors.issue_tag_webhook_processor import (
    SentryIssueTagWebhookProcessor,
)
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
                blueprint="sentryIssueTag",
                properties={},
            )
        )
    )
    return ResourceConfig(kind="issue_tag", selector=Selector(query="true"), port=port)


@pytest.mark.asyncio
class TestSentryIssueTagWebhookProcessor:
    async def test_should_process_event(self) -> None:
        """Should always return True for issue tag events as per implementation."""
        event = WebhookEvent(trace_id="t1", payload={}, headers={})
        processor = SentryIssueTagWebhookProcessor(event)
        result = await processor._should_process_event(event)
        assert result is True

    async def test_get_matching_kinds(self) -> None:
        """Should return ['issue_tag'] for matching kinds."""
        event = WebhookEvent(trace_id="t2", payload={}, headers={})
        processor = SentryIssueTagWebhookProcessor(event)

        kinds = await processor.get_matching_kinds(event)
        assert kinds == [ObjectKind.ISSUE_TAG]

    async def test_handle_event_without_group_returns_empty(self) -> None:
        """Events without 'group' key should return empty results."""
        event = WebhookEvent(trace_id="t3", payload={}, headers={})
        processor = SentryIssueTagWebhookProcessor(event)

        payload = {
            "action": "created",
            "data": {"issue": {"id": "12345"}},
            "installation": {"uuid": "test-uuid"},
        }

        result = await processor.handle_event(payload, _resource_config())

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_handle_sentry_event_success(self) -> None:
        """Test handling of Sentry service hook events with issue tags."""
        event = WebhookEvent(trace_id="t4", payload={}, headers={})
        processor = SentryIssueTagWebhookProcessor(event)

        payload = {"group": {"id": "12345"}, "project": {"slug": "test-project"}}

        mock_client = AsyncMock()
        mock_issue = {"id": "12345", "title": "Test Issue"}
        mock_tags = [
            {"key": "environment", "value": "production"},
            {"key": "level", "value": "error"},
        ]
        mock_client.get_issue.return_value = mock_issue
        mock_client.get_issues_tags_from_issues.return_value = mock_tags

        with patch(
            "webhook_processors.issue_tag_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 2
        assert result.updated_raw_results[0]["key"] == "environment"
        assert result.updated_raw_results[1]["key"] == "level"
        assert result.deleted_raw_results == []
        mock_client.get_issue.assert_called_once_with("12345")
        mock_client.get_issues_tags_from_issues.assert_called_once_with("12345")

    async def test_handle_sentry_event_issue_not_found(self) -> None:
        """Test handling when issue is not found - should return empty results."""
        event = WebhookEvent(trace_id="t5", payload={}, headers={})
        processor = SentryIssueTagWebhookProcessor(event)

        payload = {"group": {"id": "12345"}, "project": {"slug": "test-project"}}

        mock_client = AsyncMock()
        mock_client.get_issue.return_value = None

        with patch(
            "webhook_processors.issue_tag_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, _resource_config())

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        mock_client.get_issue.assert_called_once_with("12345")
        mock_client.get_issues_tags_from_issues.assert_not_called()

    async def test_handle_sentry_event_no_tags(self) -> None:
        """Test handling when issue exists but has no tags."""
        event = WebhookEvent(trace_id="t6", payload={}, headers={})
        processor = SentryIssueTagWebhookProcessor(event)

        payload = {"group": {"id": "12345"}, "project": {"slug": "test-project"}}

        mock_client = AsyncMock()
        mock_issue = {"id": "12345", "title": "Test Issue"}
        mock_client.get_issue.return_value = mock_issue
        mock_client.get_issues_tags_from_issues.return_value = []

        with patch(
            "webhook_processors.issue_tag_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, _resource_config())

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        mock_client.get_issue.assert_called_once_with("12345")
        mock_client.get_issues_tags_from_issues.assert_called_once_with("12345")

    async def test_handle_sentry_event_multiple_tags(self) -> None:
        """Test handling when issue has multiple tags."""
        event = WebhookEvent(trace_id="t7", payload={}, headers={})
        processor = SentryIssueTagWebhookProcessor(event)

        payload = {"group": {"id": "67890"}, "project": {"slug": "another-project"}}

        mock_client = AsyncMock()
        mock_issue = {"id": "67890", "title": "Another Issue"}
        mock_tags = [
            {"key": "browser", "value": "Chrome"},
            {"key": "os", "value": "Windows"},
            {"key": "device", "value": "Desktop"},
            {"key": "release", "value": "v1.2.3"},
        ]
        mock_client.get_issue.return_value = mock_issue
        mock_client.get_issues_tags_from_issues.return_value = mock_tags

        with patch(
            "webhook_processors.issue_tag_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 4
        assert result.deleted_raw_results == []
