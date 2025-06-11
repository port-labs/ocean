from typing import cast
from loguru import logger
from initialize_client import create_jira_client
from jira.overrides import JiraIncidentResourceConfig
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


class JSMIncidentWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        # JSM incidents from OpsGenie integration typically come through specific events
        webhook_event = event.payload.get("webhookEvent", "")
        return "incident" in webhook_event.lower() or self._is_incident_event(
            event.payload
        )

    def _is_incident_event(self, payload: EventPayload) -> bool:
        """Check if the event is related to JSM incidents."""
        # Look for incident-specific fields or event types
        issue = payload.get("issue", {})
        fields = issue.get("fields", {})
        issue_type = fields.get("issuetype", {}).get("name", "")

        return "incident" in issue_type.lower() or "problem" in issue_type.lower()

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.INCIDENT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = create_jira_client()
        config = cast(JiraIncidentResourceConfig, resource_config)

        # For incidents, we might need to extract incident ID differently
        incident_id = payload.get("incident", {}).get("id") or payload.get(
            "issue", {}
        ).get("key")

        logger.info(f"Processing JSM incident webhook for incident: {incident_id}")

        if payload.get("webhookEvent") == "incident_deleted":
            logger.info(f"JSM incident {incident_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": incident_id}],
            )

        try:
            # Get the incident details from JSM OpsGenie API
            incident_data = await client.get_single_incident(incident_id)

            # Filter by status if specified in config
            if (
                config.selector.status
                and incident_data.get("status") != config.selector.status
            ):
                logger.info(
                    f"Incident {incident_id} filtered out - status doesn't match"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"id": incident_id}],
                )

            return WebhookEventRawResults(
                updated_raw_results=[incident_data],
                deleted_raw_results=[],
            )
        except Exception as e:
            logger.warning(
                f"Failed to fetch JSM incident {incident_id}: {e}, removing from sync"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": incident_id}],
            )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
