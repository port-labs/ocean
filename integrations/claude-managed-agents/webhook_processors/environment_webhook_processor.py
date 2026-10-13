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

ENVIRONMENT_EVENTS_PREFIX = "environment."
ENVIRONMENT_DELETE_EVENTS = {"environment.deleted"}


class EnvironmentWebhookProcessor(AbstractAnthropicWebhookProcessor):
    """Keeps `environment` entities in sync from environment webhooks."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return self.get_event_type(event.payload).startswith(ENVIRONMENT_EVENTS_PREFIX)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ENVIRONMENT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        event_type = self.get_event_type(payload)
        environment_id = self.get_resource_id(payload)

        if event_type in ENVIRONMENT_DELETE_EVENTS:
            logger.info(
                f"Deleting environment {environment_id} from catalog ({event_type})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": environment_id}],
            )

        client = create_anthropic_client()
        environment = await client.get_environment(environment_id)
        logger.info(
            f"Upserting environment {environment_id} from catalog ({event_type})"
        )
        return WebhookEventRawResults(
            updated_raw_results=[environment.to_dict(mode="json")],
            deleted_raw_results=[],
        )
