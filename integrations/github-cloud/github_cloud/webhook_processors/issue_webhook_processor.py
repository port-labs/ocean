from loguru import logger

from github_cloud.helpers.utils import ObjectKind
from github_cloud.helpers.constants import ISSUE_DELETE_EVENTS, ISSUE_UPSERT_EVENTS
from initialize_client import init_client
from github_cloud.webhook_processors.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

class IssueWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")

        return (
            event_name == "issues"
            and event_type in ISSUE_UPSERT_EVENTS + ISSUE_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload.get("action")
        issue = payload.get("issue", {})
        repo_name = payload.get("repository", {}).get("name")
        issue_number = issue.get("number")

        logger.info(f"Processing issue event: {action} for {repo_name}#{issue_number}")

        if action in ISSUE_DELETE_EVENTS:
            logger.info(f"Issue #{issue_number} was deleted in {repo_name}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[issue],
            )

        client = init_client()
        latest_issue = await client.get_single_resource(ObjectKind.ISSUE, f"{repo_name}/{issue_number}")

        logger.info(f"Successfully retrieved recent data for issue {repo_name}#{issue_number}")

        return WebhookEventRawResults(updated_raw_results=[latest_issue], deleted_raw_results=[])
