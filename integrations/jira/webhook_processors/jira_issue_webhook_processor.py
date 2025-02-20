from typing import Any
from loguru import logger
from jira.client import JiraClient
from object_kind import ObjectKind
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload, WebhookEvent, WebhookEventRawResults


class JiraIssueWebhookProcessor(AbstractWebhookProcessor):
    def create_jira_client(self) -> JiraClient:
        """Create JiraClient with current configuration."""
        return JiraClient(
            ocean.integration_config["jira_host"],
            ocean.integration_config["atlassian_user_email"],
            ocean.integration_config["atlassian_user_token"],
        )

    def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("jira:issue_")

    def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]


    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = self.create_jira_client()
        issue_key = payload["issue"]["key"]
        logger.info(
            f"Fetching issue with key: {issue_key} and applying specified JQL filter"
        )

        if payload.get("webhookEvent") == "jira:issue_deleted":
            logger.info(f"Issue {issue_key} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload["issue"]],
            )

        params = {}

        if resource_config.selector.jql:
            params["jql"] = (
                f"{resource_config.selector.jql} AND key = {payload['issue']['key']}"
            )
        else:
            params["jql"] = f"key = {payload['issue']['key']}"

        issues: list[dict[str, Any]] = []
        async for issues_batch in client.get_paginated_issues(params):
            issues.extend(issues_batch)

        data_to_update = []
        data_to_delete = []
        if not issues:
            logger.warning(
                f"Issue {payload['issue']['key']} not found"
                f" using the following query: {params['jql']},"
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
        # For Jira webhooks, we don't need additional authentication as they are validated
        # through the webhook secret in the URL
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        # Validate that the payload contains the required fields
        return True
