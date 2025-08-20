from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from loguru import logger
from checkmarx_one.utils import ObjectKind
from checkmarx_one.exporter_factory import create_scan_exporter
from checkmarx_one.core.options import SingleScanOptions
from .abstract_webhook_processor import CheckmarxOneAbstractWebhookProcessor


class ScanWebhookProcessor(CheckmarxOneAbstractWebhookProcessor):
    """Processes scan-related webhook events from Checkmarx One."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event is a scan-related event."""
        event_type = event.payload.get("event_type", "")
        return event_type in ["Completed Scan", "Failed Scan", "Partial Scan"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SCAN]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the scan webhook event and return the raw results."""
        logger.info("Processing scan webhook event from Checkmarx One")

        # Extract scan information from the webhook payload
        scan_data = payload.get("scan", {})
        if not scan_data:
            logger.warning("No scan data found in webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        scan_id = scan_data.get("id")
        if not scan_id:
            logger.warning("No scan ID found in webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        event_type = payload.get("event_type", "")
        logger.info(f"Processing scan: {scan_id} with event type: {event_type}")

        # Get the full scan details using the scan exporter
        scan_exporter = create_scan_exporter()
        try:
            options = SingleScanOptions(scan_id=scan_id)
            full_scan_data = await scan_exporter.get_resource(options)
            if full_scan_data:
                return WebhookEventRawResults(
                    updated_raw_results=[full_scan_data],
                    deleted_raw_results=[],
                )
            else:
                logger.warning(f"Could not retrieve scan details for ID: {scan_id}")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )
        except Exception as e:
            logger.error(f"Error retrieving scan details: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required scan fields."""
        return "scan" in payload and "event_type" in payload
