from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from jira.client import COMMENT_WEBHOOK_EVENTS
from jira.comments import normalize_issue_comment
from kinds import Kinds
from webhook_processors.jira_abstract_webhook_processor import (
    JiraAbstractWebhookProcessor,
)


class IssueCommentWebhookProcessor(JiraAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent") in COMMENT_WEBHOOK_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.ISSUE_COMMENT]

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        comment = payload.get("comment")
        issue = payload.get("issue")
        if not isinstance(comment, dict) or not comment.get("id"):
            return False
        return isinstance(issue, dict) and bool(issue.get("key"))

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        comment = payload["comment"]
        issue_key = payload["issue"]["key"]
        webhook_event = payload.get("webhookEvent")
        normalized = normalize_issue_comment(comment, issue_key)
        logger.info(f"Processing {webhook_event} for {normalized['__commentId']}")

        if webhook_event == "comment_deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[normalized],
            )
        return WebhookEventRawResults(
            updated_raw_results=[normalized],
            deleted_raw_results=[],
        )
