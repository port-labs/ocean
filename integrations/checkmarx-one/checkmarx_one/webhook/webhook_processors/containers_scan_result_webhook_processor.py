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
    create_scan_exporter,
)
from checkmarx_one.utils import ScanResultObjectKind
from integration import CheckmarxOneScanResultResourcesConfig
from checkmarx_one.webhook.webhook_processors.scan_webhook_processor import (
    ScanWebhookProcessor,
)


class ContainersScanResultWebhookProcessor(ScanWebhookProcessor):
    """Processes containers scan result related webhook events from Checkmarx One."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ScanResultObjectKind.CONTAINERS]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the containers scan result webhook event and return the raw results."""

        scan_id = payload["scanId"]
        project_id = payload["projectId"]
        branch = payload["branch"]

        logger.info(
            f"Processing containers scan result for scan: {scan_id} of project: {project_id}"
        )

        scan_result_exporter = create_scan_result_exporter()
        selector = cast(CheckmarxOneScanResultResourcesConfig, resource_config).selector

        options = ListScanResultOptions(
            type=ScanResultObjectKind.CONTAINERS,
            scan_id=scan_id,
            project_id=project_id,
            branch=branch,
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
            f"Fetched {len(data_to_upsert)} containers scan results for scan {scan_id}"
        )

        data_to_delete = []
        if selector.scan_filter.latest_scans_only and self._is_scan_fully_completed():
            scan_exporter = create_scan_exporter()
            previous_scan = await scan_exporter.get_previous_completed_scan(
                project_id, branch, scan_id
            )
            if previous_scan:
                prev_scan_id = previous_scan["id"]
                prev_options = ListScanResultOptions(
                    type=ScanResultObjectKind.CONTAINERS,
                    scan_id=prev_scan_id,
                    project_id=project_id,
                    branch=branch,
                    severity=selector.severity,
                    state=selector.state,
                    status=selector.status,
                    exclude_result_types=selector.exclude_result_types,
                )
                async for prev_batch in scan_result_exporter.get_paginated_resources(
                    prev_options
                ):
                    data_to_delete.extend(prev_batch)
                logger.info(
                    f"Queued {len(data_to_delete)} previous containers findings from scan {prev_scan_id} for deletion"
                )

        return WebhookEventRawResults(
            updated_raw_results=data_to_upsert,
            deleted_raw_results=data_to_delete,
        )
