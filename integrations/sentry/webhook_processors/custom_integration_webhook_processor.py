from typing import Any

from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from webhook_processors.base_webhook_processor import _SentryBaseWebhookProcessor
from integration import ObjectKind
from webhook_processors.event import DELETE_ACTION, EVENT_ACTIONS


class SentryCustomIntegrationWebhookProcessor(_SentryBaseWebhookProcessor):
    """Processor for Sentry custom integration webhooks."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the integration webhook payload."""
        issue_id = payload.get("data", {}).get("issue", {}).get("id")
        action = payload.get("action")
        return issue_id is not None and action is not None

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this is an issue webhook event."""
        return (
            event.payload.get("action") in EVENT_ACTIONS
            and event.headers.get("sentry-hook-resource") == "issue"
        )

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
