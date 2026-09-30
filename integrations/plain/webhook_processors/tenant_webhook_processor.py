from __future__ import annotations

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from plain.client import PlainClient
from plain.constants import TENANT_EVENTS
from plain.utils import ObjectKind
from webhook_processors.plain_abstract_webhook_processor import (
    PlainAbstractWebhookProcessor,
)
from webhook_processors.utils import event_payload, tenant_id_from_payload


class TenantWebhookProcessor(PlainAbstractWebhookProcessor):
    """Plain has no tenant.* webhooks; refresh tenant from thread.tenant_updated."""

    def get_event_types(self) -> set[str]:
        return set(TENANT_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.TENANT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        body = event_payload(payload)
        tenant_id = tenant_id_from_payload(body)
        if not tenant_id:
            logger.info("Plain tenant webhook has no tenant id; skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = PlainClient()
        tenant = await client.get_tenant(tenant_id)
        logger.info("Upserting Plain tenant {}", tenant_id)
        return WebhookEventRawResults(
            updated_raw_results=[tenant],
            deleted_raw_results=[],
        )
