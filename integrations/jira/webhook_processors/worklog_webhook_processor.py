from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from kinds import Kinds
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from jira.client import WORKLOG_WEBHOOK_EVENTS
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)

from initialize_client import get_or_create_jira_client


class WorklogWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent") in WORKLOG_WEBHOOK_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.WORKLOG]

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        worklog = payload.get("worklog")
        if not worklog or not isinstance(worklog, dict):
            return False
        return bool(worklog.get("id"))

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        worklog = payload["worklog"]
        webhook_event = payload.get("webhookEvent")

        if webhook_event == "worklog_deleted":
            logger.info(
                f"Worklog {worklog.get('id')} deleted on issue {worklog.get('issueId')}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[worklog],
            )

        issue_id = worklog.get("issueId")
        if not issue_id:
            logger.warning(
                f"Worklog {worklog.get('id')} has no issueId, cannot enrich — skipping"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        client = get_or_create_jira_client()
        issue = await client.get_single_issue(str(issue_id))

        if not issue:
            logger.warning(
                f"Issue {issue_id} not found for worklog {worklog.get('id')} — skipping"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        enriched_worklog = {**worklog, "__issueKey": issue.get("key")}
        return WebhookEventRawResults(
            updated_raw_results=[enriched_worklog],
            deleted_raw_results=[],
        )
