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

VAULT_EVENTS = ("vault.",)
VAULT_DELETE_EVENTS = {"vault.deleted"}


class VaultWebhookProcessor(AbstractAnthropicWebhookProcessor):
    """Keeps `vault` entities in sync from vault webhooks."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return self.get_event_type(event.payload).startswith(VAULT_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.VAULT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        event_type = self.get_event_type(payload)
        data = payload.get("data") or {}

        if event_type in VAULT_DELETE_EVENTS:
            vault_id = data.get("id")
            logger.info(f"Deleting vault {vault_id} from catalog ({event_type})")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": vault_id}]
            )

        vault_id = str(data.get("id") or "")
        client = create_anthropic_client()
        vault = await client.get_vault(vault_id)
        logger.info(f"Upserting vault {vault_id} from catalog ({event_type})")
        return WebhookEventRawResults(
            updated_raw_results=[vault], deleted_raw_results=[]
        )
