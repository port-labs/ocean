from loguru import logger

from initialize_client import init_client
from kinds import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.base_webhook_processor import StatuspageBaseWebhookProcessor


class PageWebhookProcessor(StatuspageBaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return "page" in event.payload

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PAGE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        page = payload.get("page")
        return isinstance(page, dict) and "id" in page

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        page_id = payload["page"]["id"]
        client = init_client()
        page = await client.get_page_by_id(page_id)
        logger.debug(f"Received page: {page}")

        return WebhookEventRawResults(
            updated_raw_results=[{**payload["page"], **page}],
            deleted_raw_results=[],
        )
