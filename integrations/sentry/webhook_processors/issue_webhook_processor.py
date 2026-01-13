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
from webhook_processors.init_client import init_webhook_client


class SentryIssueWebhookProcessor(_SentryBaseWebhookProcessor):
    """Processor for Sentry issue webhooks."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this is an issue webhook event."""
        return True

    def _validate_integration_payload(self, payload: EventPayload) -> bool:
        """Validate the integration webhook payload."""
        if payload.get("group", {}).get("id") and payload.get("project", {}).get(
            "slug"
        ):
            return True
        return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process issue webhook events."""
        if "group" in payload:
            return await self._handle_sentry_event(payload, resource_config)

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def _handle_sentry_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process Sentry issue webhook events."""
        issue_id = payload["group"]["id"]

        logger.info(f"Processing Sentry issue webhook: issue_id={issue_id}")

        updated_results: list[dict[str, Any]] = []
        deleted_results: list[dict[str, Any]] = []

        client = init_webhook_client()
        issue = await client.get_issue(issue_id)
        if issue:
            updated_results.append(issue)
        else:
            deleted_results.append({"id": issue_id})

        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=deleted_results
        )
