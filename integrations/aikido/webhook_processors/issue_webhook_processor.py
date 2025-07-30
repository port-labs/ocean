from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from loguru import logger
from integration import ObjectKind
from .base_webhook_processor import BaseAikidoWebhookProcessor


class IssueWebhookProcessor(BaseAikidoWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUES]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle issue webhook events from Aikido.
        Extract issue data from the webhook payload.
        """
        logger.info("Processing issue webhook event from Aikido")

        issue_id = payload["payload"]["issue_id"]
        issue_data = await self._webhook_client.get_issue(issue_id)
        if not issue_data:
            logger.warning("No issue data found in webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        logger.info(f"Processing issue: {issue_data.get('id', 'unknown')}")

        return WebhookEventRawResults(
            updated_raw_results=[issue_data],
            deleted_raw_results=[],
        )
