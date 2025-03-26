from loguru import logger
from client import GitHubClient
from consts import ISSUE_DELETE_EVENTS, ISSUE_UPSERT_EVENTS
from helpers.utils import ObjectKind
from webhook_processors.abstract import GitHubAbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

class IssueWebhookProcessor(GitHubAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.payload.get("action") in ISSUE_UPSERT_EVENTS
            or event.payload.get("action") in ISSUE_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = GitHubClient.from_ocean_config()
        issue = payload.get("issue", {})
        repo = payload.get("repository", {})
        
        if payload.get("action") in ISSUE_DELETE_EVENTS:
            logger.info(f"Issue #{issue.get('number')} was deleted in {repo.get('name')}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[issue],
            )

        logger.info(f"Got event for issue #{issue.get('number')}: {payload.get('action')}")
        return WebhookEventRawResults(
            updated_raw_results=[issue],
            deleted_raw_results=[],
        ) 