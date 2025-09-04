from typing import cast
from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from checkmarx_one.core.options import (
    ListScanResultOptions,
)
from checkmarx_one.exporter_factory import (
    create_scan_result_exporter,
)
from checkmarx_one.utils import ScanResultObjectKind
from .scan_webhook_processor import ScanWebhookProcessor
from integration import CheckmarxOneScanResultResourcesConfig


class ScaScanResultWebhookProcessor(ScanWebhookProcessor):
    """Processes sca scan result related webhook events from Checkmarx One."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ScanResultObjectKind.SCA]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the sca scan result webhook event and return the raw results."""

        scan_id = payload["scanId"]
        project_id = payload["projectId"]

        logger.info(
            f"Processing sca scan result for scan: {scan_id} of project: {project_id}"
        )

        scan_result_exporter = create_scan_result_exporter()
        selector = cast(CheckmarxOneScanResultResourcesConfig, resource_config).selector

        options = ListScanResultOptions(
            type=ScanResultObjectKind.SCA,
            scan_id=scan_id,
            severity=selector.severity,
            state=selector.state,
            status=selector.status,
            exclude_result_types=selector.exclude_result_types,
        )

        data_to_upsert = []
        async for result_data_list in scan_result_exporter.get_paginated_resources(
            options
        ):
            data_to_upsert.extend(result_data_list)

        logger.info(
            f"Fetched {len(data_to_upsert)} sca scan results for scan {scan_id}"
        )

        return WebhookEventRawResults(
            updated_raw_results=data_to_upsert,
            deleted_raw_results=[],
        )
