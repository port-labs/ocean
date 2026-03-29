from typing import cast
from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from checkmarx_one.core.options import (
    ListKicsOptions,
)
from checkmarx_one.exporter_factory import (
    create_kics_exporter,
    create_scan_exporter,
)
from checkmarx_one.utils import ObjectKind
from integration import (
    CheckmarxOneKicsResourcesConfig,
)
from checkmarx_one.webhook.webhook_processors.scan_webhook_processor import (
    ScanWebhookProcessor,
)


class KicsScanResultWebhookProcessor(ScanWebhookProcessor):
    """Processes kics scan result related webhook events from Checkmarx One."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.KICS]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the kics scan result webhook event and return the raw results."""

        scan_id = payload["scanId"]
        project_id = payload["projectId"]
        branch = payload["branch"]

        logger.info(
            f"Processing KICS scan result for scan: {scan_id} of project: {project_id}"
        )

        kics_exporter = create_kics_exporter()
        selector = cast(CheckmarxOneKicsResourcesConfig, resource_config).selector

        options = ListKicsOptions(
            scan_id=scan_id,
            project_id=project_id,
            branch=branch,
            severity=selector.severity,
            status=selector.status,
        )

        data_to_upsert = []
        async for result_data_list in kics_exporter.get_paginated_resources(options):
            data_to_upsert.extend(result_data_list)

        logger.info(
            f"Fetched {len(data_to_upsert)} KICS scan results for scan {scan_id} from Webhook"
        )

        data_to_delete = []
        if selector.scan_filter.latest_scans_only:
            scan_exporter = create_scan_exporter()
            previous_scan = await scan_exporter.get_previous_completed_scan(
                project_id, branch, scan_id
            )
            if previous_scan:
                prev_scan_id = previous_scan["id"]
                prev_options = ListKicsOptions(
                    scan_id=prev_scan_id,
                    project_id=project_id,
                    branch=branch,
                    severity=selector.severity,
                    status=selector.status,
                )
                async for prev_batch in kics_exporter.get_paginated_resources(
                    prev_options
                ):
                    data_to_delete.extend(prev_batch)
                logger.info(
                    f"Queued {len(data_to_delete)} previous KICS findings from scan {prev_scan_id} for deletion"
                )

        return WebhookEventRawResults(
            updated_raw_results=data_to_upsert,
            deleted_raw_results=data_to_delete,
        )
