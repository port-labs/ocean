from loguru import logger
from github.webhooks_processors.processors._abstract_webhook_processor import (
    BaseWebhookProcessorMixin,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from github.webhooks_processors.events import Events


WEBHOOK_NAME = "GithubPingWebhook"


class GithubPingWebhookProcessor(BaseWebhookProcessorMixin):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        logger.info(f"[{WEBHOOK_NAME}] Should process event")
        event_type = self._get_github_event_type(event.headers)
        if event_type != Events.PING.value:
            logger.info(f"[{WEBHOOK_NAME}] Skipping non-ping event: {event_type}")
            return False
        logger.info(f"[{WEBHOOK_NAME}] Processing ping event")
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        # Ping does not create entities; return empty list
        logger.info(f"[{WEBHOOK_NAME}] Matching kinds: [] for ping")
        return []

    async def validate_payload(self, payload: EventPayload) -> bool:
        # GitHub ping payload typically contains a zen and hook object
        valid = isinstance(payload, dict) and "zen" in payload and "hook" in payload
        if not valid:
            logger.warning(f"[{WEBHOOK_NAME}] Invalid ping payload structure")
        return valid


    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        logger.info(f"[{WEBHOOK_NAME}] Handling ping event")
        # No entities to upsert/delete for ping; it's just a handshake
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])


