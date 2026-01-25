from loguru import logger
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.misc import Kind
from azure_devops.webhooks.events import AdvancedSecurityAlertEvents
from azure_devops.client.azure_devops_client import (
    AzureDevopsClient,
    ADVANCED_SECURITY_PUBLISHER_ID,
)
from urllib.parse import unquote
from typing import cast
from integration import AzureDevopsAdvancedSecurityResourceConfig


class AdvancedSecurityWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.ADVANCED_SECURITY_ALERT]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        if payload["publisherId"] != ADVANCED_SECURITY_PUBLISHER_ID:
            return False

        project_id = payload.get("resourceContainers", {}).get("project", {}).get("id")
        return (
            project_id is not None
            and "repositoryUrl" in payload["resource"]
            and "alertId" in payload["resource"]
            and "state" in payload["resource"]
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            return bool(AdvancedSecurityAlertEvents(event_type))
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        raw_security_alert = payload["resource"]
        alert_id = raw_security_alert["alertId"]

        selector = cast(
            AzureDevopsAdvancedSecurityResourceConfig, resource_config
        ).selector
        alert_state = raw_security_alert["state"]
        if (
            selector.criteria
            and selector.criteria.states
            and alert_state not in selector.criteria.states
        ):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        project_id = payload["resourceContainers"]["project"]["id"]
        project = await client.get_single_project(project_id)
        if not project:
            logger.warning(
                f"Project with ID {project_id} not found, cannot enrich advanced security alert"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        repository_url = raw_security_alert["repositoryUrl"]
        repository_id = unquote(repository_url.split("/")[-1])
        repository = await client.get_repository(repository_id)
        if not repository:
            logger.warning(
                f"Repository with ID {repository_id} not found, cannot enrich advanced security alert"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        security_alert = await client.get_single_advanced_security_alert(
            project_id, repository_id, alert_id
        )
        if not security_alert:
            logger.warning(
                f"ID {alert_id} not found, cannot enrich advanced security alert"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )
        enriched_security_alert = client._enrich_security_alert(
            security_alert, repository
        )
        return WebhookEventRawResults(
            updated_raw_results=[enriched_security_alert],
            deleted_raw_results=[],
        )
