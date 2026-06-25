from loguru import logger

from kinds import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook.consts import WebhookPayloadKey
from webhook.webhook_processors.base_webhook_processor import BaseWebhookProcessor


class PageWebhookProcessor(BaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return WebhookPayloadKey.PAGE in event.payload

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PAGE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        page = payload.get(WebhookPayloadKey.PAGE)
        return isinstance(page, dict) and "id" in page

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        page_id = payload[WebhookPayloadKey.PAGE]["id"]
        page = await self.client.get_page_by_id(page_id)
        logger.debug(f"Received page: {page}")

        return WebhookEventRawResults(
            updated_raw_results=[{**payload[WebhookPayloadKey.PAGE], **page}],
            deleted_raw_results=[],
        )
