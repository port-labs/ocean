from typing import Any, cast

from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from webhook_processors.base_webhook_processor import _SentryBaseWebhookProcessor
from integration import ObjectKind, SentryResourceConfig
from webhook_processors.init_client import init_webhook_client


class SentryIssueTagWebhookProcessor(_SentryBaseWebhookProcessor):
    """Processor for Sentry issue tag webhooks."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE_TAG]

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the integration webhook payload."""
        return payload.get("group", {}).get("id") is not None

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this is an issue webhook event."""
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process issue webhook events."""
        issue_id = payload["group"]["id"]

        logger.info(f"Processing Sentry issue tag webhook: issue_id={issue_id}")

        updated_results: list[dict[str, Any]] = []
        deleted_results: list[dict[str, Any]] = []

        client = init_webhook_client()
        issue = await client.get_issue(issue_id)
        if issue:
            selector = cast(SentryResourceConfig, resource_config).selector
            issue_tags = await client.get_issues_tags_from_issues(selector.tag, [issue])
            updated_results.extend(issue_tags)
        else:
            deleted_results.append({"id": issue_id})

        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=deleted_results
        )
