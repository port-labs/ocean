from typing import Any, List
from webhook.processors._base_processor import (
    ServicenowAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from integration import ObjectKind
from webhook.initialize_client import initialize_webhook_client


class ServiceCatalogWebhookProcessor(ServicenowAbstractWebhookProcessor):
    """Service Catalog webhook processor."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SERVICE_CATALOG]

    def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("sys_class_name") == ObjectKind.SERVICE_CATALOG

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        sys_id = payload["sys_id"]

        updated_raw_results: List[dict[str, Any]] = []
        deleted_raw_results: List[dict[str, Any]] = []

        client = initialize_webhook_client()
        sc_catalog = await client.get_record_by_sys_id(
            ObjectKind.SERVICE_CATALOG, sys_id
        )

        if sc_catalog:
            updated_raw_results.append(sc_catalog)
        else:
            deleted_raw_results.append(payload)

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )
