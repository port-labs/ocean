from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from checkmarx_one.core.options import SingleScanOptions
from checkmarx_one.exporter_factory import create_scan_exporter
from checkmarx_one.utils import ObjectKind
from checkmarx_one.webhook.events import CheckmarxEventType
from .abstract_webhook_processor import _CheckmarxOneAbstractWebhookProcessor


class ScanWebhookProcessor(_CheckmarxOneAbstractWebhookProcessor):
    """Processes scan-related webhook events from Checkmarx One."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        return {"scanId", "projectId"} <= payload.keys()

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event is a scan-related event."""
        return event.headers.get("x-cx-webhook-event") in [
            CheckmarxEventType.SCAN_COMPLETED,
            CheckmarxEventType.SCAN_FAILED,
            CheckmarxEventType.SCAN_PARTIAL,
        ]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SCAN]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the scan webhook event and return the raw results."""

        scan_id = payload["scanId"]
        project_id = payload["projectId"]

        logger.info(f"Processing scan: {scan_id} of project: {project_id}")

        scan_exporter = create_scan_exporter()
        data_to_upsert = await scan_exporter.get_resource(
            SingleScanOptions(scan_id=scan_id)
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert],
            deleted_raw_results=[],
        )
