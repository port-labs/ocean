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

AGENT_EVENTS_PREFIX = "agent."
AGENT_DELETE_EVENTS = {"agent.deleted"}


class AgentWebhookProcessor(AbstractAnthropicWebhookProcessor):
    """Keeps `agent` entities in sync from agent webhooks."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return self.get_event_type(event.payload).startswith(AGENT_EVENTS_PREFIX)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.AGENT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        event_type = self.get_event_type(payload)
        agent_id = self.get_resource_id(payload)

        if event_type in AGENT_DELETE_EVENTS:
            logger.info(f"Deleting agent {agent_id} from catalog ({event_type})")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": agent_id}]
            )

        client = create_anthropic_client()
        agent = await client.get_agent(agent_id)
        logger.info(f"Upserting agent {agent_id} from catalog ({event_type})")
        return WebhookEventRawResults(
            updated_raw_results=[agent.to_dict(mode="json")],
            deleted_raw_results=[],
        )
