from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from jira_server.webhook_processors.events import JiraDeletedIssueEvent
from jira_server.webhook_processors.processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)


@pytest.fixture
def webhook_event() -> WebhookEvent:
    return WebhookEvent(
        payload={
            "webhookEvent": "jira:issue_created",
            "issue": {
                "id": "99291",
                "self": "https://jira.atlassian.com/rest/api/2/issue/99291",
                "key": "JRA-20002",
                "fields": {
                    "summary": "I feel the need for speed",
                    "created": "2009-12-16T23:46:10.612-0600",
                    "description": "Make the issue nav load 10x faster",
                    "labels": ["UI", "dialogue", "move"],
                    "priority": "Minor",
                },
            },
        },
        headers={},
        trace_id="test-trace-id",
    )


@pytest.fixture
def issue_webhook_processor(webhook_event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(webhook_event)


@pytest.mark.asyncio
class TestIssueWebhookProcessor:
    async def test_should_process_event_true(
        self,
        issue_webhook_processor: IssueWebhookProcessor,
        webhook_event: WebhookEvent,
    ) -> None:
        assert await issue_webhook_processor.should_process_event(webhook_event) is True

    async def test_should_process_event_false(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            payload={"webhookEvent": "some:other_event"},
            headers={},
            trace_id="test-trace-id",
        )
        assert await issue_webhook_processor.should_process_event(event) is False

    async def test_validate_payload_valid(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        payload = {"webhookEvent": "jira:issue_created", "issue": {}}
        assert await issue_webhook_processor.validate_payload(payload) is True

    async def test_validate_payload_invalid(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        assert await issue_webhook_processor.validate_payload({}) is False
        assert (
            await issue_webhook_processor.validate_payload({"webhookEvent": "event"})
            is False
        )
        assert await issue_webhook_processor.validate_payload({"issue": {}}) is False

    async def test_handle_event_issue_created(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        payload = {
            "webhookEvent": "jira:issue_created",
            "issue": {
                "id": "99291",
                "self": "https://jira.atlassian.com/rest/api/2/issue/99291",
                "key": "TEST-1",
                "fields": {
                    "summary": "I feel the need for speed",
                    "created": "2009-12-16T23:46:10.612-0600",
                    "description": "Make the issue nav load 10x faster",
                    "labels": ["UI", "dialogue", "move"],
                    "priority": "Minor",
                },
            },
        }
        resource_config = AsyncMock()
        mock_client = AsyncMock()
        mock_client.get_single_issue.return_value = payload["issue"]
        with patch(
            "jira_server.webhook_processors.processors.issue_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            results = await issue_webhook_processor.handle_event(
                payload, resource_config
            )

        assert len(results.updated_raw_results) == 1
        assert results.updated_raw_results[0]["key"] == "TEST-1"
        assert len(results.deleted_raw_results) == 0

    async def test_handle_event_issue_deleted(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        payload = {
            "webhookEvent": JiraDeletedIssueEvent,
            "issue": {
                "id": "99291",
                "self": "https://jira.atlassian.com/rest/api/2/issue/99291",
                "key": "TEST-1",
                "fields": {
                    "summary": "I feel the need for speed",
                    "created": "2009-12-16T23:46:10.612-0600",
                    "description": "Make the issue nav load 10x faster",
                    "labels": ["UI", "dialogue", "move"],
                    "priority": "Minor",
                },
            },
        }
        resource_config = AsyncMock()

        mock_client = AsyncMock()
        mock_client.get_single_issue.return_value = payload["issue"]

        with patch(
            "jira_server.webhook_processors.processors.issue_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            results = await issue_webhook_processor.handle_event(
                payload, resource_config
            )

        assert len(results.updated_raw_results) == 0
        assert len(results.deleted_raw_results) == 1
        assert results.deleted_raw_results[0]["key"] == "TEST-1"
