from __future__ import annotations

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from plain.client import PlainClient
from plain.constants import COMPANY_EVENTS
from plain.utils import ObjectKind
from webhook_processors.plain_abstract_webhook_processor import (
    PlainAbstractWebhookProcessor,
)
from webhook_processors.utils import customer_id_from_payload, entity_id, event_payload


class CompanyWebhookProcessor(PlainAbstractWebhookProcessor):
    """Plain has no company.* webhooks; refresh company from customer events."""

    def get_event_types(self) -> set[str]:
        return set(COMPANY_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.COMPANY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        body = event_payload(payload)
        customer_id = customer_id_from_payload(body)
        if not customer_id:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = PlainClient()
        customer = await client.get_customer(customer_id)
        company_id = entity_id(customer.get("company"))
        if not company_id:
            logger.info(
                "Plain customer {} has no company; skipping company live update",
                customer_id,
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        company = await client.get_company(company_id)
        logger.info("Upserting Plain company {} from customer event", company_id)
        return WebhookEventRawResults(
            updated_raw_results=[company],
            deleted_raw_results=[],
        )
