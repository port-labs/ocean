from __future__ import annotations

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from plain.client import PlainClient
from plain.constants import CUSTOMER_DELETE_EVENTS, CUSTOMER_EVENTS
from plain.utils import ObjectKind
from webhook_processors.plain_abstract_webhook_processor import (
    PlainAbstractWebhookProcessor,
)
from webhook_processors.utils import (
    customer_id_from_payload,
    event_payload,
    event_type,
)


class CustomerWebhookProcessor(PlainAbstractWebhookProcessor):
    def get_event_types(self) -> set[str]:
        return set(CUSTOMER_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.CUSTOMER]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        body = event_payload(payload)
        kind = event_type(payload)
        if kind in CUSTOMER_DELETE_EVENTS:
            customer_id = customer_id_from_payload(body, deleted=True)
            if not customer_id:
                logger.warning("Plain customer delete webhook missing id; skipping")
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )
            logger.info("Deleting Plain customer {}", customer_id)
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": customer_id}],
            )

        customer_id = customer_id_from_payload(body)
        if not customer_id:
            logger.warning("Plain customer webhook missing id; skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = PlainClient()
        customer = await client.get_customer(customer_id)
        logger.info("Upserting Plain customer {}", customer_id)
        return WebhookEventRawResults(
            updated_raw_results=[customer],
            deleted_raw_results=[],
        )
