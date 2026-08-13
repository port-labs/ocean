from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from clients.client_factory import create_anthropic_client
from integration import ObjectKind
from webhook_processors.abstract_webhook_processor import (
    AbstractAnthropicWebhookProcessor,
)

SESSION_EVENT_PREFIX = "session."
SESSION_DELETE_EVENTS = {"session.deleted"}


class SessionWebhookProcessor(AbstractAnthropicWebhookProcessor):
    """Keeps `session` entities in sync from session lifecycle webhooks."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return self.get_event_type(event.payload).startswith(SESSION_EVENT_PREFIX)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SESSION]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        event_type = self.get_event_type(payload)
        session_id = self.get_resource_id(payload)

        if event_type in SESSION_DELETE_EVENTS:
            logger.info(f"Deleting session {session_id} from catalog ({event_type})")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": session_id}]
            )

        client = create_anthropic_client()
        session = await client.get_session(session_id)
        logger.info(f"Upserting session {session_id} from catalog ({event_type})")
        return WebhookEventRawResults(
            updated_raw_results=[session], deleted_raw_results=[]
        )
