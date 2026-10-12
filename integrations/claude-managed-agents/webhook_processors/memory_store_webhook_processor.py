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

MEMORY_STORE_EVENTS_PREFIX = "memory_store."
MEMORY_STORE_DELETE_EVENTS = {"memory_store.deleted"}


class MemoryStoreWebhookProcessor(AbstractAnthropicWebhookProcessor):
    """Keeps `memory-store` entities in sync from memory_store webhooks."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return self.get_event_type(event.payload).startswith(MEMORY_STORE_EVENTS_PREFIX)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MEMORY_STORE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        event_type = self.get_event_type(payload)
        memory_store_id = self.get_resource_id(payload)

        if event_type in MEMORY_STORE_DELETE_EVENTS:
            logger.info(
                f"Deleting memory store {memory_store_id} from catalog ({event_type})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": memory_store_id}],
            )

        client = create_anthropic_client()
        memory_store = await client.get_memory_store(memory_store_id)
        logger.info(
            f"Upserting memory store {memory_store_id} from catalog ({event_type})"
        )
        return WebhookEventRawResults(
            updated_raw_results=[memory_store.to_dict(mode="json")],
            deleted_raw_results=[],
        )
