from loguru import logger
from typing import Any, cast

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from webhook_processors.base_webhook_processor import _SentryBaseWebhookProcessor
from integration import ObjectKind, IssueResourceConfig
from webhook_processors.events import ARCHIVED_ISSUE_ACTION


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

        selector = cast(IssueResourceConfig, resource_config).selector
        if action == ARCHIVED_ISSUE_ACTION and not selector.include_archived:
            deleted_results.append(issue)
        else:
            updated_results.append(issue)

        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=deleted_results
        )
