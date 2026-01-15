from loguru import logger
from typing import Any
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from kinds import Kinds
from jira_server.webhook_processors.events import JiraIssueEvents, JiraDeletedIssueEvent


class IssueWebhookProcessor(AbstractWebhookProcessor):

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.ISSUE]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("webhookEvent")
        return event_type in JiraIssueEvents

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "webhookEvent" in payload and "issue" in payload

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        issue = payload["issue"]
        event_type = payload["webhookEvent"]
        logger.info(
            f"Processing issue webhook event: {event_type} for issue {issue.get('key')}"
        )

        updated_raw_results: list[dict[str, Any]] = []
        deleted_raw_results: list[dict[str, Any]] = []
        if event_type == JiraDeletedIssueEvent:
            deleted_raw_results.append(issue)
        else:
            updated_raw_results.append(issue)

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )
