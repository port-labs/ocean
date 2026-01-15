import pytest
from unittest.mock import AsyncMock, patch

from webhook_processors.issue_tag_webhook_processor import (
    SentryIssueTagWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import ObjectKind, IssueResourceConfig, IssueSelector


def _resource_config() -> IssueResourceConfig:
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
    return IssueResourceConfig(
        kind="issue-tag",
        selector=IssueSelector(query="true"),
        port=port,
    )


@pytest.mark.asyncio
class TestSentryIssueTagWebhookProcessor:
    async def test_should_process_event(self) -> None:
        """Should return True for issue events as per implementation."""
        event = WebhookEvent(
            trace_id="t1",
            payload={"action": "created", "data": {"issue": {"id": "12345"}}},
            headers={
                "sentry-hook-resource": "issue",
                "sentry-hook-signature": "test-signature",
            },
        )
        processor = SentryIssueTagWebhookProcessor(event)
        result = await processor.should_process_event(event)
        assert result is True

    async def test_get_matching_kinds(self) -> None:
        """Should return ['issue_tag'] for matching kinds."""
        event = WebhookEvent(
            trace_id="t2",
            payload={},
            headers={
                "sentry-hook-resource": "issue",
                "sentry-hook-signature": "test-signature",
            },
        )
        processor = SentryIssueTagWebhookProcessor(event)

        kinds = await processor.get_matching_kinds(event)
        assert kinds == [ObjectKind.ISSUE_TAG]

    async def test_handle_sentry_event_success(self) -> None:
        """Test handling of Sentry service hook events with issue tags."""
        event = WebhookEvent(
            trace_id="t4",
            payload={},
            headers={
                "sentry-hook-resource": "issue",
                "sentry-hook-signature": "test-signature",
            },
        )
        processor = SentryIssueTagWebhookProcessor(event)

        payload = {
            "action": "created",
            "data": {
                "issue": {"id": "12345", "title": "Test Issue"},
                "project": {"slug": "test-project"},
            },
        }

        mock_client = AsyncMock()
        mock_issue = {"id": "12345", "title": "Test Issue"}
        mock_tags = [
            {"key": "environment", "value": "production"},
            {"key": "level", "value": "error"},
        ]
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
        mock_client.get_issues_tags_from_issues.assert_called_once_with(
            "environment", [mock_issue]
        )

    async def test_handle_sentry_event_no_tags(self) -> None:
        """Test handling when issue exists but has no tags."""
        event = WebhookEvent(
            trace_id="t6",
            payload={},
            headers={
                "sentry-hook-resource": "issue",
                "sentry-hook-signature": "test-signature",
            },
        )
        processor = SentryIssueTagWebhookProcessor(event)

        payload = {
            "action": "created",
            "data": {
                "issue": {"id": "12345", "title": "Test Issue"},
                "project": {"slug": "test-project"},
            },
        }

        mock_client = AsyncMock()
        mock_issue = {"id": "12345", "title": "Test Issue"}
        mock_client.get_issues_tags_from_issues.return_value = []

        with patch(
            "webhook_processors.issue_tag_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, _resource_config())

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        mock_client.get_issues_tags_from_issues.assert_called_once_with(
            "environment", [mock_issue]
        )

    async def test_handle_sentry_event_multiple_tags(self) -> None:
        """Test handling when issue has multiple tags."""
        event = WebhookEvent(
            trace_id="t7", payload={}, headers={"sentry-hook-resource": "issue"}
        )
        processor = SentryIssueTagWebhookProcessor(event)

        payload = {
            "action": "created",
            "data": {"issue": {"id": "67890"}, "project": {"slug": "another-project"}},
        }

        mock_client = AsyncMock()
        mock_tags = [
            {"key": "browser", "value": "Chrome"},
            {"key": "os", "value": "Windows"},
            {"key": "device", "value": "Desktop"},
            {"key": "release", "value": "v1.2.3"},
        ]
        mock_client.get_issues_tags_from_issues.return_value = mock_tags

        with patch(
            "webhook_processors.issue_tag_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 4
        assert result.deleted_raw_results == []

    async def test_handle_sentry_event_delete(self) -> None:
        """Test handling when issue is deleted."""
        event = WebhookEvent(
            trace_id="t8", payload={}, headers={"sentry-hook-resource": "issue"}
        )
        processor = SentryIssueTagWebhookProcessor(event)

        payload = {
            "action": "ignored",
            "data": {"issue": {"id": "67890"}, "project": {"slug": "another-project"}},
        }

        mock_client = AsyncMock()
        mock_tags = [
            {"key": "browser", "value": "Chrome"},
            {"key": "os", "value": "Windows"},
            {"key": "device", "value": "Desktop"},
            {"key": "release", "value": "v1.2.3"},
        ]
        mock_client.get_issues_tags_from_issues.return_value = mock_tags

        with patch(
            "webhook_processors.issue_tag_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            resource_config = _resource_config()
            resource_config.selector.include_archived = False
            result = await processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 4
