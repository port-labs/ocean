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
    APPLICATION_EVALUATION_EVENT,
    POLICY_MANAGEMENT_EVENT,
    SonatypeAbstractWebhookProcessor,
)


class ApplicationWebhookProcessor(SonatypeAbstractWebhookProcessor):
    """Keep application entities fresh.

    Triggered both when an application is evaluated (in case its metadata
    changed) and when a Policy Management event reports an APPLICATION-type
    owner was updated.
    """

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_id = self._event_id(event)
        payload = event.payload
        if event_id == APPLICATION_EVALUATION_EVENT:
            return "applicationEvaluation" in payload
        if event_id == POLICY_MANAGEMENT_EVENT:
            return payload.get("owner", {}).get("type") == "APPLICATION"
        return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.APPLICATION]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if "applicationEvaluation" in payload:
            return "publicId" in payload["applicationEvaluation"].get("application", {})
        return "publicId" in payload.get("owner", {})

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = get_sonatype_client()
        if "applicationEvaluation" in payload:
            public_id = payload["applicationEvaluation"]["application"]["publicId"]
        else:
            public_id = payload["owner"]["publicId"]

        application = await client.get_application_by_public_id(public_id)
        if not application:
            logger.warning(f"Application '{public_id}' not found; skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(f"Refreshing application entity '{public_id}'")
        return WebhookEventRawResults(
            updated_raw_results=[application],
            deleted_raw_results=[],
        )
