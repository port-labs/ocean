from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result

from mend.core.exporters.abstract_exporter import AbstractMendExporter
from mend.core.options import ListProjectOptions, SingleProjectOptions


class MendProjectExporter(AbstractMendExporter):
    async def get_resource(self, options: SingleProjectOptions) -> RAW_ITEM:
        response = await self.client.send_api_request(
            f"/api/v3.0/orgs/{self.client.org_uuid}/projects/{options['project_uuid']}/summaries"
        )
        items: list[dict[str, Any]] = response.get("response", [])
        return items[0] if items else {}

    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: ListProjectOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        endpoint = f"/api/v3.0/orgs/{options['org_uuid']}/projects/summaries"
        async for batch in self.client.send_cursor_paginated_request(
            endpoint, method="POST", json_data={}
        ):
            logger.info(f"Fetched batch of {len(batch)} projects")
            yield batch

    async def get_changed_projects(
        self,
        options: ListProjectOptions,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns all project summaries whose lastScanned or creationDate is newer than `since`.
        When `since` is None every project is returned (full sync path).

        Reuses the cached output of get_paginated_resources within the same resync
        event, so the project list is fetched from Mend at most once per sync.
        """
        changed: List[Dict[str, Any]] = []

        async for batch in self.get_paginated_resources(options):
            for project in batch:
                if since is None or self._is_changed(project, since):
                    changed.append(project)

        label = since.isoformat() if since else "beginning"
        logger.info(f"Delta check: {len(changed)} project(s) changed since {label}")
        return changed

    @staticmethod
    def _is_changed(project: Dict[str, Any], since: datetime) -> bool:
        since_ts = since.timestamp()

        # lastScanTime lives under statistics and is a Unix ms timestamp
        last_scan_ms = (
            project.get("statistics", {}).get("LAST_SCAN", {}).get("lastScanTime")
        )
        if last_scan_ms:
            try:
                if int(last_scan_ms) / 1000 > since_ts:
                    return True
            except (ValueError, TypeError):
                pass

        # creationDate is an ISO datetime string
        creation_date = project.get("creationDate")
        if creation_date:
            try:
                ts = datetime.fromisoformat(creation_date.replace("Z", "+00:00"))
                if ts.timestamp() > since_ts:
                    return True
            except ValueError:
                pass

        return False
