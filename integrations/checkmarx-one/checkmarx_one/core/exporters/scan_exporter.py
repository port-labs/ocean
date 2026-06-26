from typing import Any, Optional
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from port_ocean.utils.cache import cache_iterator_result
from checkmarx_one.core.options import SingleScanOptions, ListScanOptions


class CheckmarxScanExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One scans."""

    async def get_resource(
        self,
        options: SingleScanOptions,
    ) -> RAW_ITEM:
        """Get a specific scan by ID."""
        response = await self.client.send_api_request(f"/scans/{options['scan_id']}")
        logger.info(f"Fetched scan with ID: {options['scan_id']}")
        return response

    @cache_iterator_result()
    async def get_paginated_resources(
        self,
        options: ListScanOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get scans from Checkmarx One.

        When `latest_scans_only=True`, forces `sort=-created_at` and
        `statuses=Completed`, then streams pages yielding only the first
        (newest) scan encountered per `(projectId, branch)` group.

        Yields:
            Batches of scans
        """
        latest_scans_only = options.get("latest_scans_only", False)
        params: dict[str, Any] = self._get_params(options)

        if latest_scans_only:
            params["sort"] = "-created_at"
            params["statuses"] = ["Completed"]

            seen_groups: set[tuple[str, str]] = set()
            async for scans in self.client.send_paginated_request(
                "/scans", "scans", params
            ):
                filtered_batch = []
                for scan in scans:
                    project_id = scan.get("projectId", "")
                    branch = scan.get("branch", "")
                    group_key = (project_id, branch)
                    if group_key not in seen_groups:
                        seen_groups.add(group_key)
                        filtered_batch.append(scan)
                if filtered_batch:
                    logger.info(
                        f"Fetched batch of {len(scans)} scans, yielding {len(filtered_batch)} after dedup (latest_scans_only)"
                    )
                    yield filtered_batch
        else:
            async for scans in self.client.send_paginated_request(
                "/scans", "scans", params
            ):
                logger.info(f"Fetched batch of {len(scans)} scans")
                yield scans

    async def get_previous_completed_scan(
        self,
        project_id: str,
        branch: str,
        current_scan_id: str,
    ) -> Optional[dict[str, Any]]:
        """
        Return the most recent completed scan for `project_id` + `branch`
        that is not `current_scan_id`.

        Queries `/api/scans` with sort=-created_at so results arrive
        newest-first.  Skips the entry matching `current_scan_id` and
        returns the next one found.  Returns None if no prior scan exists.

        NOTE: Intentionally bypasses @cache_iterator_result so the result
        always reflects the live state of the API.
        """
        params: dict[str, Any] = {
            "project-id": project_id,
            "branches": [branch],
            "statuses": ["Completed"],
            "sort": "-created_at",
        }
        async for scans in self.client.send_paginated_request(
            "/scans", "scans", params
        ):
            for scan in scans:
                if scan.get("id") != current_scan_id:
                    logger.info(
                        f"Found previous completed scan {scan.get('id')} for project {project_id} branch {branch}"
                    )
                    return scan
        return None

    def _get_params(self, options: ListScanOptions) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if project_names := options.get("project_names"):
            params["project-names"] = project_names
        if project_id_filter := options.get("project_id_filter"):
            params["project-id"] = project_id_filter
        if branches := options.get("branches"):
            params["branches"] = branches
        if statuses := options.get("statuses"):
            params["statuses"] = statuses
        if from_date := options.get("from_date"):
            params["from-date"] = from_date
        return params
