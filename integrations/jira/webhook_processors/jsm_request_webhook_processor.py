from typing import cast
from loguru import logger
from initialize_client import create_jira_client
from jira.overrides import JiraRequestResourceConfig
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


class JSMRequestWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        # JSM request events are typically prefixed with "jira:issue_" for service requests
        webhook_event = event.payload.get("webhookEvent", "")
        return webhook_event.startswith("jira:issue_") and self._is_service_request(
            event.payload
        )

    def _is_service_request(self, payload: EventPayload) -> bool:
        """Check if the issue is a service request from JSM."""
        issue = payload.get("issue", {})
        fields = issue.get("fields", {})

        # JSM requests typically have specific issue types or custom fields
        issue_type = fields.get("issuetype", {}).get("name", "")
        project = fields.get("project", {})

        # Check if it's a service desk project or has service request characteristics
        return (
            "Service Request" in issue_type
            or "Incident" in issue_type
            or project.get("projectTypeKey") == "service_desk"
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = create_jira_client()
        config = cast(JiraRequestResourceConfig, resource_config)
        issue_key = payload["issue"]["key"]

        logger.info(f"Fetching JSM request with key: {issue_key}")

        if payload.get("webhookEvent") == "jira:issue_deleted":
            logger.info(f"JSM request {issue_key} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload["issue"]],
            )

        try:
            # Get the request details from JSM API
            request_data = await client.get_single_request(issue_key)

            # Filter by service desk if specified in config
            if (
                config.selector.service_desk_id
                and str(request_data.get("serviceDeskId"))
                != config.selector.service_desk_id
            ):
                logger.info(
                    f"Request {issue_key} filtered out - not from specified service desk"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[payload["issue"]],
                )

            return WebhookEventRawResults(
                updated_raw_results=[request_data],
                deleted_raw_results=[],
            )
        except Exception as e:
            logger.warning(
                f"Failed to fetch JSM request {issue_key}: {e}, removing from sync"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload["issue"]],
            )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
