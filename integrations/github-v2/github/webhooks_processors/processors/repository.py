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
from github.kind.object_kind import ObjectKind


WEBHOOK_NAME = "GithubRepositoryWebhook"


class GithubRepositoryWebhookProcessor(BaseWebhookProcessorMixin):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = self._get_github_event_type(event.headers)
        if event_type != Events.REPOSITORY.value:
            logger.info(f"[{WEBHOOK_NAME}] Skipping event type: {event_type}")
            return False
        logger.info(f"[{WEBHOOK_NAME}] Processing repository event: action={event.payload.get('action')}")
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY.value]

    async def validate_payload(self, payload: EventPayload) -> bool:
        has_repo = isinstance(payload, dict) and isinstance(payload.get("repository"), dict)
        has_name = has_repo and isinstance(payload["repository"].get("name"), str)
        if not (has_repo and has_name):
            logger.warning(f"[{WEBHOOK_NAME}] Invalid payload structure for repository webhook")
            return False
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        repo = dict(payload.get("repository", {}))
        result = WebhookEventRawResults(updated_raw_results=[repo], deleted_raw_results=[])
        
        logger.info(f"[{WEBHOOK_NAME}] Handle event result = {len(result.updated_raw_results)}")
        
        return result


