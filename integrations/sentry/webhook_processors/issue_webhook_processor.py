from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from webhook_processors.base_webhook_processor import _SentryBaseWebhookProcessor
from integration import ObjectKind


class SentryIssueWebhookProcessor(_SentryBaseWebhookProcessor):
    """Processor for Sentry issue webhooks."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the integration webhook payload."""
        return payload.get("group", {}).get("id") is not None

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this is an issue webhook event."""
        # return event.headers.get("")
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process issue webhook events."""
        issue_id = payload["group"]["id"]
        logger.info(f"Processing Sentry issue webhook: issue_id={issue_id}")
        issue = payload["group"]

        return WebhookEventRawResults(
            updated_raw_results=[issue], deleted_raw_results=[]
        )
