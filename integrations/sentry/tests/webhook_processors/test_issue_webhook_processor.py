import pytest

from webhook_processors.issue_webhook_processor import SentryIssueWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import ObjectKind, IssueSelector, IssueResourceConfig


def _resource_config() -> IssueResourceConfig:
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
    return IssueResourceConfig(
        kind="issue",
        selector=IssueSelector(query="true"),
        port=port,
    )


@pytest.mark.asyncio
class TestSentryIssueWebhookProcessor:
    async def test_should_process_event(self) -> None:
        """Should return True for issue events with the correct header value and action in payload"""
        event = WebhookEvent(
            trace_id="t1",
            payload={"action": "created", "data": {"issue": {"id": "12345"}}},
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "issue",
            },
        )
        processor = SentryIssueWebhookProcessor(event)
        result = await processor.should_process_event(event)
        assert result is True

    async def test_get_matching_kinds(self) -> None:
        """Should return [ObjectKind.ISSUE] for matching kinds."""
        event = WebhookEvent(
            trace_id="t10",
            payload={
                "action": "created",
            },
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "issue",
            },
        )
        processor = SentryIssueWebhookProcessor(event)

        kinds = await processor.get_matching_kinds(event)
        assert kinds == [ObjectKind.ISSUE]

    async def test_validate_payload_valid(self) -> None:
        """Payload with data.id and project.slug should be valid."""
        event = WebhookEvent(
            trace_id="t2",
            payload={},
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "issue",
            },
        )
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "created",
            "data": {
                "issue": {
                    "id": "12345",
                    "title": "Test Issue",
                }
            },
        }
        result = await processor.validate_payload(payload)
        assert result is True

    async def test_validate_payload_missing_issue(self) -> None:
        """Payload without data.issue should be invalid."""
        event = WebhookEvent(
            trace_id="t3",
            payload={},
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "issue",
            },
        )
        processor = SentryIssueWebhookProcessor(event)

        payload = {"action": "created", "data": {}}
        result = await processor.validate_payload(payload)
        assert result is False

    async def test_handle_sentry_event_success(self) -> None:
        """Test handling of Sentry service hook events with active issue."""
        event = WebhookEvent(
            trace_id="t6",
            payload={},
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "issue",
            },
        )
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "created",
            "data": {"issue": {"id": "12345"}},
            "project": {"slug": "test-project"},
        }

        result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["id"] == "12345"
        assert result.deleted_raw_results == []

    async def test_handle_sentry_event_with_different_issue_id(self) -> None:
        """Test handling with a different issue ID."""
        event = WebhookEvent(
            trace_id="t8",
            payload={},
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "issue",
            },
        )
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "created",
            "data": {"issue": {"id": "67890"}},
            "project": {"slug": "another-project"},
        }

        result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["id"] == "67890"
        assert result.deleted_raw_results == []

    async def test_handle_sentry_event_with_archived_issue_if_selector_includes_archived(
        self,
    ) -> None:
        """Test handling of Sentry service hook events with archived issue if selector includes archived."""
        event = WebhookEvent(
            trace_id="t9",
            payload={},
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "issue",
            },
        )
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "ignored",
            "data": {"issue": {"id": "12345"}},
            "project": {"slug": "test-project"},
        }

        resource_config = _resource_config()
        resource_config.selector.include_archived = True
        result = await processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0

    async def test_handle_sentry_event_with_archived_issue_if_selector_excludes_archived(
        self,
    ) -> None:
        """Test handling of Sentry service hook events with archived issue if selector excludes archived."""
        event = WebhookEvent(
            trace_id="t10",
            payload={},
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "issue",
            },
        )
        processor = SentryIssueWebhookProcessor(event)

        payload = {
            "action": "ignored",
            "data": {"issue": {"id": "12345"}},
            "project": {"slug": "test-project"},
        }

        resource_config = _resource_config()
        resource_config.selector.include_archived = False
        result = await processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
