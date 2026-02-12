from typing import cast
from loguru import logger
from initialize_client import create_jira_client
from jira.overrides import JiraIssueConfig
from kinds import Kinds
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class IssueWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("jira:issue_")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = create_jira_client()
        config = cast(JiraIssueConfig, resource_config)
        issue_key = payload["issue"]["key"]
        issue_id = int(payload["issue"]["id"])
        logger.info(
            f"Fetching issue with key: {issue_key} and applying specified JQL filter"
        )

        if payload.get("webhookEvent") == "jira:issue_deleted":
            logger.info(f"Issue {issue_key} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload["issue"]],
            )

        jql = f"key = {issue_key}"
        if config.selector.jql:
            jql = f"({config.selector.jql}) AND key = {issue_key}"

        issues = await client.search_issues_by_ids(
            jql=jql,
            issue_ids=[issue_id],
            fields=config.selector.fields,
        )

        data_to_update = []
        data_to_delete = []
        if not issues:
            logger.warning(
                f"Issue {payload['issue']['key']} not found"
                f" using the following query: {jql},"
                " trying to remove..."
            )
            data_to_delete.append(payload["issue"])
        else:
            data_to_update.extend(issues)

        return WebhookEventRawResults(
            updated_raw_results=data_to_update,
            deleted_raw_results=data_to_delete,
        )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "issue" in payload
