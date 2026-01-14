import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
    Selector,
)
from integration import ObjectKind
from webhook_processors.custom_integration_webhook_processor import (
    SentryCustomIntegrationWebhookProcessor,
)
from webhook_processors.events import DELETE_ACTION


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
class TestSentryCustomIntegrationWebhookProcessor:
    async def test_get_matching_kinds(self) -> None:
        """Should return [ObjectKind.ISSUE] for matching kinds."""
        event = WebhookEvent(trace_id="t1", payload={}, headers={})
        processor = SentryCustomIntegrationWebhookProcessor(event)

        kinds = await processor.get_matching_kinds(event)
        assert kinds == [ObjectKind.ISSUE]

    async def test_validate_payload_valid(self) -> None:
        """Payload with data.issue.id and action should be valid."""
        event = WebhookEvent(trace_id="t2", payload={}, headers={})
        processor = SentryCustomIntegrationWebhookProcessor(event)

        payload = {
            "data": {"issue": {"id": "12345"}},
            "action": "created",
        }
        result = await processor.validate_payload(payload)
        assert result is True

    async def test_validate_payload_invalid_missing_issue_id(self) -> None:
        """Payload without issue id should be invalid."""
        event = WebhookEvent(trace_id="t3", payload={}, headers={})
        processor = SentryCustomIntegrationWebhookProcessor(event)

        payload = {
            "data": {"issue": {}},
            "action": "created",
        }
        result = await processor.validate_payload(payload)
        assert result is False

    async def test_validate_payload_invalid_missing_action(self) -> None:
        """Payload without action should be invalid."""
        event = WebhookEvent(
            trace_id="t4", payload={}, headers={"sentry-hook-resource": "issue"}
        )
        processor = SentryCustomIntegrationWebhookProcessor(event)

        payload = {
            "data": {"issue": {"id": "12345"}},
        }
        result = await processor.validate_payload(payload)
        assert result is False

    async def test_should_process_event_valid(self) -> None:
        """Should process event with valid action and correct header."""
        payload = {"action": "created"}
        headers = {"sentry-hook-resource": "issue"}
        event = WebhookEvent(trace_id="t5", payload=payload, headers=headers)
        processor = SentryCustomIntegrationWebhookProcessor(event)

        result = await processor._should_process_event(event)
        assert result is True

    async def test_should_process_event_invalid_action(self) -> None:
        """Should not process event with invalid action."""
        payload = {"action": "some_other_action"}
        headers = {"sentry-hook-resource": "issue"}
        event = WebhookEvent(trace_id="t6", payload=payload, headers=headers)
        processor = SentryCustomIntegrationWebhookProcessor(event)

        result = await processor._should_process_event(event)
        assert result is False

    async def test_should_process_event_invalid_header(self) -> None:
        """Should not process event with invalid header."""
        payload = {"action": "created"}
        headers = {"sentry-hook-resource": "something_else"}
        event = WebhookEvent(trace_id="t7", payload=payload, headers=headers)
        processor = SentryCustomIntegrationWebhookProcessor(event)

        result = await processor._should_process_event(event)
        assert result is False

    async def test_handle_event_updated(self) -> None:
        """Test handling of event that should update the issue."""
        payload = {
            "action": "created",
            "data": {"issue": {"id": "12345", "title": "New Issue"}},
        }
        event = WebhookEvent(trace_id="t8", payload=payload, headers={})
        processor = SentryCustomIntegrationWebhookProcessor(event)

        result = await processor.handle_event(payload, _resource_config())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["id"] == "12345"
        assert result.updated_raw_results[0]["title"] == "New Issue"
        assert result.deleted_raw_results == []

    async def test_handle_event_deleted(self) -> None:
        """Test handling of event that should delete the issue."""
        payload = {
            "action": DELETE_ACTION,
            "data": {"issue": {"id": "12345"}},
        }
        event = WebhookEvent(trace_id="t9", payload=payload, headers={})
        processor = SentryCustomIntegrationWebhookProcessor(event)

        result = await processor.handle_event(payload, _resource_config())

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["id"] == "12345"
