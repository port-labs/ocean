from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from loguru import logger
from checkmarx_one.utils import ObjectKind
from checkmarx_one.exporter_factory import create_scan_result_exporter
from checkmarx_one.core.options import ListScanResultOptions
from .abstract_webhook_processor import CheckmarxOneAbstractWebhookProcessor


class ScanResultWebhookProcessor(CheckmarxOneAbstractWebhookProcessor):
    """Processes scan result-related webhook events from Checkmarx One."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event is a scan completion event that may have results."""
        event_type = event.payload.get("event_type", "")
        return event_type == "Completed Scan"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SCAN_RESULT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the scan result webhook event and return the raw results."""
        logger.info("Processing scan result webhook event from Checkmarx One")

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

        logger.info(f"Processing scan results for scan: {scan_id}")

        # Get the scan results using the scan result exporter
        scan_result_exporter = create_scan_result_exporter()
        try:
            options = ListScanResultOptions(scan_id=scan_id)
            scan_results = []
            async for batch in scan_result_exporter.get_paginated_resources(options):
                scan_results.extend(batch)

            if scan_results:
                logger.info(
                    f"Retrieved {len(scan_results)} scan results for scan {scan_id}"
                )
                return WebhookEventRawResults(
                    updated_raw_results=scan_results,
                    deleted_raw_results=[],
                )
            else:
                logger.warning(f"No scan results found for scan ID: {scan_id}")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )
        except Exception as e:
            logger.error(f"Error retrieving scan results: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required scan fields."""
        return "scan" in payload and "event_type" in payload
