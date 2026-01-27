from typing import Any
from checkmarx_one.core.options import SingleApplicationOptions
from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from checkmarx_one.exporter_factory import create_application_exporter
from checkmarx_one.utils import ObjectKind
from checkmarx_one.webhook.events import CheckmarxEventType
from checkmarx_one.webhook.webhook_processors.abstract_webhook_processor import (
    _CheckmarxOneAbstractWebhookProcessor,
)
from integration import CheckmarxOneApplicationResourcesConfig
from typing import cast


class ApplicationWebhookProcessor(_CheckmarxOneAbstractWebhookProcessor):
    """Processes application-related webhook events from Checkmarx One."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required application fields."""
        return "ID" in payload

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event is a application-related event."""
        return (
            event.headers.get("x-cx-webhook-event")
            == CheckmarxEventType.APPLICATION_CREATED
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the application kind for this webhook processor."""
        return [ObjectKind.APPLICATION]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the application webhook event and return the raw results."""

        application_id = payload["ID"]

        logger.info(f"Processing application: {application_id}")

        selector = cast(
            CheckmarxOneApplicationResourcesConfig, resource_config
        ).selector
        tag_keys = selector.tag_keys
        tag_values = selector.tag_values

        if not self._check_tag_keys_filter(payload, tag_keys):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        if not self._check_tag_values_filter(payload, tag_values):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        application_exporter = create_application_exporter()
        data_to_upsert = await application_exporter.get_resource(
            SingleApplicationOptions(application_id=application_id)
        )

        logger.info(f"Processed data for application: {application_id}")

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert],
            deleted_raw_results=[],
        )

    def _check_tag_keys_filter(
        self, application: dict[str, Any], tag_keys: list[str]
    ) -> bool:
        if not tag_keys:
            return True
        return any(tag_key in application["tags"] for tag_key in tag_keys)

    def _check_tag_values_filter(
        self, application: dict[str, Any], tag_values: list[str]
    ) -> bool:
        if not tag_values:
            return True
        return any(tag_value in application["tags"].values() for tag_value in tag_values)
