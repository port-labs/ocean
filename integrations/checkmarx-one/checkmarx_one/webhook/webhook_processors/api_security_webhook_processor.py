from typing import cast
from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from checkmarx_one.core.options import ListApiSecOptions
from checkmarx_one.exporter_factory import create_api_sec_exporter, create_scan_exporter
from checkmarx_one.utils import ObjectKind
from integration import CheckmarxOneApiSecResourcesConfig
from checkmarx_one.webhook.webhook_processors.scan_webhook_processor import (
    ScanWebhookProcessor,
)


class ApiSecurityWebhookProcessor(ScanWebhookProcessor):
    """Processes scan api security related webhook events from Checkmarx One."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.API_SEC]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the scan webhook event and return the raw results."""

        scan_id = payload["scanId"]
        project_id = payload["projectId"]
        branch = payload["branch"]

        logger.info(
            f"Processing api security for scan: {scan_id} of project: {project_id}"
        )

        api_sec_exporter = create_api_sec_exporter()
        selector = cast(CheckmarxOneApiSecResourcesConfig, resource_config).selector

        data_to_upsert = []
        async for batch in api_sec_exporter.get_paginated_resources(
            ListApiSecOptions(scan_id=scan_id, branch=branch)
        ):
            data_to_upsert.extend(batch)

        logger.info(
            f"Processed {len(data_to_upsert)} API security results for scan: {scan_id}"
        )

        data_to_delete = []
        if selector.scan_filter.latest_scans_only:
            scan_exporter = create_scan_exporter()
            previous_scan = await scan_exporter.get_previous_completed_scan(
                project_id, branch, scan_id
            )
            if previous_scan:
                prev_scan_id = previous_scan["id"]
                async for prev_batch in api_sec_exporter.get_paginated_resources(
                    ListApiSecOptions(scan_id=prev_scan_id, branch=branch)
                ):
                    data_to_delete.extend(prev_batch)
                logger.info(
                    f"Queued {len(data_to_delete)} previous API sec findings from scan {prev_scan_id} for deletion"
                )

        return WebhookEventRawResults(
            updated_raw_results=data_to_upsert,
            deleted_raw_results=data_to_delete,
        )
