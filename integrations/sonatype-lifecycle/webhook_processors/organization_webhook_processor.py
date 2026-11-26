from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from initialize_client import get_sonatype_client
from kinds import ObjectKind
from webhook_processors._base import (
    POLICY_MANAGEMENT_EVENT,
    SonatypeAbstractWebhookProcessor,
)


class OrganizationWebhookProcessor(SonatypeAbstractWebhookProcessor):
    """Refresh an organization entity on ORGANIZATION Policy Management events."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            self._event_id(event) == POLICY_MANAGEMENT_EVENT
            and event.payload.get("owner", {}).get("type") == "ORGANIZATION"
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ORGANIZATION]

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "id" in payload.get("owner", {})

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = get_sonatype_client()
        organization_id = payload["owner"]["id"]
        organization = await client.get_single_organization(organization_id)
        if not organization:
            logger.warning(f"Organization '{organization_id}' not found; skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(f"Refreshing organization entity '{organization_id}'")
        return WebhookEventRawResults(
            updated_raw_results=[organization],
            deleted_raw_results=[],
        )
