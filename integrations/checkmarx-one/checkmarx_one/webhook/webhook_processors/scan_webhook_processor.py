from typing import cast, Any, Optional, List

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
from integration import CheckmarxOneScanResourcesConfig, CheckmarxOneScanSelector
from .abstract_webhook_processor import _CheckmarxOneAbstractWebhookProcessor


class ScanWebhookProcessor(_CheckmarxOneAbstractWebhookProcessor):
    """Processes scan-related webhook events from Checkmarx One."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        return {"scanId", "projectId", "branch", "statusInfo"} <= payload.keys()

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

        empty_results = WebhookEventRawResults(
            updated_raw_results=[], deleted_raw_results=[]
        )
        selector = cast(CheckmarxOneScanResourcesConfig, resource_config).selector
        if not self._filter_scan_by_branches(payload, selector.branches):
            logger.warning(
                f"Scan {scan_id} of project {project_id} skipped due to branch filter"
            )
            return empty_results

        if not self._filter_scan_by_project_names(payload, selector.project_names):
            logger.warning(
                f"Scan {scan_id} of project {project_id} skipped due to project name filter"
            )
            return empty_results

        if not self._filter_scan_by_statuses(payload, selector):
            logger.warning(
                f"Scan {scan_id} of project {project_id} skipped due to status filter"
            )
            return empty_results

        scan_exporter = create_scan_exporter()
        data_to_upsert = await scan_exporter.get_resource(
            SingleScanOptions(scan_id=scan_id)
        )

        logger.info(f"Processed scan data for scan: {scan_id} in project: {project_id}")

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert],
            deleted_raw_results=[],
        )

    @staticmethod
    def _filter_scan_by_branches(
        scan: dict[str, Any], branches: Optional[List[str]]
    ) -> bool:
        if not branches:
            return True

        return scan["branch"] in branches

    @staticmethod
    def _filter_scan_by_statuses(
        scan: dict[str, Any], selector: CheckmarxOneScanSelector
    ) -> bool:
        statuses = selector.statuses
        if not statuses:
            return True

        status_info = scan["statusInfo"]
        scan_statuses = {info["status"] for info in status_info if "status" in info}
        return bool(scan_statuses & set(statuses))

    @staticmethod
    def _filter_scan_by_project_names(
        scan: dict[str, Any], project_names: Optional[List[str]]
    ) -> bool:
        logger.info(
            f"Filtering scan by project names: {project_names} for scan: {scan}"
        )
        if not project_names:
            return True

        return scan["projectId"] in project_names
