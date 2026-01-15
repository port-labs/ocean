from unittest.mock import AsyncMock

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from jira_server.webhook_processors.events import (
    JiraDeletedProjectEvent,
)
from jira_server.webhook_processors.processors.project_webhook_processor import (
    ProjectWebhookProcessor,
)


@pytest.fixture
def webhook_event() -> WebhookEvent:
    return WebhookEvent(
        payload={
            "webhookEvent": "project_created",
            "project": {"key": "TEST", "name": "Test Project"},
        },
        headers={},
        trace_id="test-trace-id",
    )


@pytest.fixture
def project_webhook_processor(webhook_event: WebhookEvent) -> ProjectWebhookProcessor:
    return ProjectWebhookProcessor(webhook_event)


@pytest.mark.asyncio
class TestProjectWebhookProcessor:
    async def test_should_process_event_true(
        self, project_webhook_processor: ProjectWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            payload={"webhookEvent": "project_created"},
            headers={},
            trace_id="test-trace-id",
        )
        assert await project_webhook_processor.should_process_event(event) is True

    async def test_should_process_event_false(
        self, project_webhook_processor: ProjectWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            payload={"webhookEvent": "some:other_event"},
            headers={},
            trace_id="test-trace-id",
        )
        assert await project_webhook_processor.should_process_event(event) is False

    async def test_validate_payload_valid(
        self, project_webhook_processor: ProjectWebhookProcessor
    ) -> None:
        payload = {"webhookEvent": "project_created", "project": {}}
        assert await project_webhook_processor.validate_payload(payload) is True

    async def test_validate_payload_invalid(
        self, project_webhook_processor: ProjectWebhookProcessor
    ) -> None:
        assert await project_webhook_processor.validate_payload({}) is False
        assert (
            await project_webhook_processor.validate_payload({"webhookEvent": "event"})
            is False
        )
        assert (
            await project_webhook_processor.validate_payload({"project": {}}) is False
        )

    async def test_handle_event_project_created(
        self, project_webhook_processor: ProjectWebhookProcessor
    ) -> None:
        payload = {
            "webhookEvent": "project_created",
            "project": {"key": "TEST", "name": "Test Project"},
        }
        resource_config = AsyncMock()

        results = await project_webhook_processor.handle_event(payload, resource_config)

        assert len(results.updated_raw_results) == 1
        assert results.updated_raw_results[0]["key"] == "TEST"
        assert len(results.deleted_raw_results) == 0

    async def test_handle_event_project_deleted(
        self, project_webhook_processor: ProjectWebhookProcessor
    ) -> None:
        payload = {
            "webhookEvent": JiraDeletedProjectEvent,
            "project": {"key": "TEST"},
        }
        resource_config = AsyncMock()

        results = await project_webhook_processor.handle_event(payload, resource_config)

        assert len(results.updated_raw_results) == 0
        assert len(results.deleted_raw_results) == 1
        assert results.deleted_raw_results[0]["key"] == "TEST"
