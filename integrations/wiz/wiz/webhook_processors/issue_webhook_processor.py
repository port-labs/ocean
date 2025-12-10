from wiz.webhook_processors._abstract_webhook_processor import (
    _WizAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from integration import ObjectKind
from overrides import IssueResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEventRawResults,
    EventPayload,
)
from loguru import logger
from wiz.options import IssueOptions
from typing import cast


class IssueWebhookProcessor(_WizAbstractWebhookProcessor):
    """Handles webhook events for issues."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        logger.info(f"Received webhook request: {payload}")

        selector = cast(IssueResourceConfig, resource_config).selector
        options = IssueOptions(
            max_pages=selector.max_pages,
            status_list=selector.status_list,
            severity_list=selector.severity_list,
            type_list=selector.type_list,
        )

        issue_id = payload["issue"]["id"]
        issue_details = await self._client.get_single_issue(issue_id, options)
        return WebhookEventRawResults(
            updated_raw_results=[issue_details],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        return (
            payload.get("issue") is not None and payload["issue"].get("id") is not None
        )
