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

        logger.info(
            f"Processing KICS scan result for scan: {scan_id} of project: {project_id}"
        )

        kics_exporter = create_kics_exporter()
        selector = cast(CheckmarxOneKicsResourcesConfig, resource_config).selector

        options = ListKicsOptions(
            scan_id=scan_id,
            severity=selector.severity,
            status=selector.status,
        )

        data_to_upsert = []
        async for result_data_list in kics_exporter.get_paginated_resources(options):
            data_to_upsert.extend(result_data_list)

        logger.info(
            f"Fetched {len(data_to_upsert)} KICS scan results for scan {scan_id} from Webhook"
        )

        return WebhookEventRawResults(
            updated_raw_results=data_to_upsert,
            deleted_raw_results=[],
        )
