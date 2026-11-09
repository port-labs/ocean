import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from webhook_processors.issue_webhook_processor import IssueWebhookProcessor


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


class TestJiraAbstractWebhookProcessorLiveEventLogIdentifiers:
    def test_includes_processor_specific_resource_ids(
        self, event: WebhookEvent
    ) -> None:
        processor = IssueWebhookProcessor(event)
        payload = {
            "webhookEvent": "worklog_created",
            "project": {"key": "ENG"},
            "user": {"accountId": "712020:abc"},
            "version": {"id": "10001"},
            "worklog": {"id": "10100", "issueId": "10002"},
            "issue": {"key": "ENG-1", "id": "10002"},
        }

        identifiers = processor.get_live_event_log_identifiers(payload, {})

        assert identifiers == {
            "webhookEvent": "worklog_created",
            "project": {"key": "ENG"},
            "user": {"accountId": "712020:abc"},
            "version": {"id": "10001"},
            "worklog": {"id": "10100"},
            "issue": {"key": "ENG-1", "id": "10002"},
        }

    def test_returns_none_when_no_matching_paths(self, event: WebhookEvent) -> None:
        processor = IssueWebhookProcessor(event)

        assert processor.get_live_event_log_identifiers({"other": "value"}, {}) is None
