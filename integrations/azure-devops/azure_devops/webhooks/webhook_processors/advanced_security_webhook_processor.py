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
from typing import cast
from integration import (
    AzureDevopsAdvancedSecurityResourceConfig,
    AdvancedSecurityFilter,
)


class AdvancedSecurityWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.ADVANCED_SECURITY_ALERT]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        project_id = payload.get("resourceContainers", {}).get("project", {}).get("id")
        return (
            project_id is not None
            and "repositoryId" in payload["resource"]
            and "alertId" in payload["resource"]
            and "state" in payload["resource"]
            and "severity" in payload["resource"]
            and "alertType" in payload["resource"]
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            if event.payload["publisherId"] != ADVANCED_SECURITY_PUBLISHER_ID:
                return False
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
        project_id = payload["resourceContainers"]["project"]["id"]
        repository_id = raw_security_alert["repositoryId"]

        selector = cast(
            AzureDevopsAdvancedSecurityResourceConfig, resource_config
        ).selector
        alert_state = raw_security_alert["state"]
        alert_severity = raw_security_alert["severity"]
        alert_type = raw_security_alert["alertType"]

        if selector.criteria:
            criteria = selector.criteria
            if not self._check_alert_type_criteria(criteria, alert_type):
                logger.info(
                    f"Advanced security alert {alert_id} filtered out: "
                    f"alert type '{alert_type}' does not match allowed type '{criteria.alert_type}'. Skipping..."
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )
            if not self._check_severity_criteria(criteria, alert_severity):
                logger.info(
                    f"Advanced security alert {alert_id} filtered out: "
                    f"severity '{alert_severity}' not in allowed severities {criteria.severities}. Skipping..."
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )
            if not self._check_state_criteria(criteria, alert_state):
                logger.info(
                    f"Advanced security alert {alert_id} filtered out: "
                    f"state '{alert_state}' not in allowed states {criteria.states}. Skipping..."
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
            security_alert, repository_id, project_id
        )
        return WebhookEventRawResults(
            updated_raw_results=[enriched_security_alert],
            deleted_raw_results=[],
        )

    def _check_state_criteria(
        self, criteria: AdvancedSecurityFilter, alert_state: str
    ) -> bool:
        if not criteria.states:
            return True
        return alert_state in criteria.states

    def _check_severity_criteria(
        self, criteria: AdvancedSecurityFilter, alert_severity: str
    ) -> bool:
        if not criteria.severities:
            return True
        return alert_severity in criteria.severities

    def _check_alert_type_criteria(
        self, criteria: AdvancedSecurityFilter, alert_type: str
    ) -> bool:
        if not criteria.alert_type:
            return True
        return alert_type == criteria.alert_type
