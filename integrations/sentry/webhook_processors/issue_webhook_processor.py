from loguru import logger
from typing import Any

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from webhook_processors.base_webhook_processor import _SentryBaseWebhookProcessor
from integration import ObjectKind
from webhook_processors.events import DELETE_ACTION


class SentryIssueWebhookProcessor(_SentryBaseWebhookProcessor):
    """Processor for Sentry issue webhooks."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process issue webhook events."""
        issue = payload["data"]["issue"]
        action = payload["action"]
        logger.info(f"Processing Sentry issue webhook: issue_id={issue['id']}")

        updated_results: list[dict[str, Any]] = []
        deleted_results: list[dict[str, Any]] = []

        if action == DELETE_ACTION:
            deleted_results.append({"id": issue["id"]})
        else:
            updated_results.append(issue)

        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=deleted_results
        )
