from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from init_client import init_client
from utils import ObjectKind
from webhook.webhook_processors.base_webhook_processor import (
    FirehydrantBaseWebhookProcessor,
)


class RetrospectiveWebhookProcessor(FirehydrantBaseWebhookProcessor):
    """Processes retrospective updates from incident live events."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return "incident" in event.payload.get("data", {})

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.RETROSPECTIVE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        incident_id = payload["data"]["incident"]["id"]
        client = init_client()
        incident_data = await client.get_single_incident(incident_id=incident_id)

        if incident_data.get("current_milestone") != "postmortem_completed":
            logger.debug(
                f"Incident {incident_id} milestone is "
                f"'{incident_data.get('current_milestone')}', skipping retrospective sync"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        retrospective_data = await client.get_single_retrospective(
            report_id=incident_data["report_id"]
        )
        return WebhookEventRawResults(
            updated_raw_results=[retrospective_data],
            deleted_raw_results=[],
        )
