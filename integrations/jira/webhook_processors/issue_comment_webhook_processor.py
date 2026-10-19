from typing import cast

from loguru import logger
from initialize_client import get_or_create_jira_client
from jira.client import COMMENT_WEBHOOK_EVENTS
from jira.comments import attach_comments_to_issues
from jira.overrides import JiraIssueConfig
from kinds import Kinds
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.jira_abstract_webhook_processor import (
    JiraAbstractWebhookProcessor,
)


class IssueCommentWebhookProcessor(JiraAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent") in COMMENT_WEBHOOK_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.ISSUE]

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
        config = cast(JiraIssueConfig, resource_config)
        empty = WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )
        if not config.selector.include_comments:
            return empty

        issue_key = payload["issue"]["key"]
        webhook_event = payload.get("webhookEvent")
        logger.info(
            f"Processing {webhook_event} for issue {issue_key} "
            f"(includeComments=true)"
        )

        client = get_or_create_jira_client()
        enriched = await attach_comments_to_issues(client, [payload["issue"]])
        return WebhookEventRawResults(
            updated_raw_results=enriched,
            deleted_raw_results=[],
        )
