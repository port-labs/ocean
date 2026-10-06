from typing import Any, List

from loguru import logger
from webhook.processors._base_processor import (
    ServicenowAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook.initialize_client import initialize_webhook_client


class GenericWebhookProcessor(ServicenowAbstractWebhookProcessor):

    def _get_table_name(self, payload: EventPayload) -> str | None:
        return payload.get("__table_name") or payload.get("sys_class_name")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        table_name = self._get_table_name(event.payload)
        return [table_name] if table_name else []

    def _should_process_event(self, event: WebhookEvent) -> bool:
        return self._get_table_name(event.payload) is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        sys_id = payload["sys_id"]
        table_name = self._get_table_name(payload)
        if not table_name:
            logger.warning("No table name found in webhook payload, skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        updated_raw_results: List[dict[str, Any]] = []
        deleted_raw_results: List[dict[str, Any]] = []

        client = initialize_webhook_client()
        record = await client.get_record_by_sys_id(table_name, sys_id)

        if record:
            updated_raw_results.append(record)
        else:
            logger.info(
                f"Record not found for {table_name}/{sys_id}, treating as delete"
            )
            deleted_raw_results.append(payload)

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )
