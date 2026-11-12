from datetime import datetime
from typing import Any

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import PaginatedExporter

# User edits to host tags or mutes, from the UI (/source/update_tags) or the API
# (/api/v1/tags/hosts/..., /api/v1/host/.../mute). The audit events don't name the
# host, so they only tell us that some host was edited.
HOST_EDITS_AUDIT_QUERY = (
    "@http.url_details.path:(*update_tags* OR *tags/hosts* OR *mute*) "
    "-@http.method:GET"
)


class HostExporter(PaginatedExporter[None]):
    async def get_paginated_resources(
        self, options: None = None, incremental_cursor: datetime | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get hosts from Datadog.
        With incremental_cursor set, only hosts that reported since then are listed,
        which includes hosts that stopped reporting after it (with up=false). Tags and
        mutes edited by users can change on hosts that no longer report, so if any
        were edited since incremental_cursor, every host is listed.
        Docs: https://docs.datadoghq.com/api/latest/hosts/#get-all-hosts-for-your-organization
        """
        url = f"{self.client.api_url}/api/v1/hosts"
        extra_params: dict[str, Any] | None = None
        if incremental_cursor and not await self._hosts_edited_since(
            incremental_cursor
        ):
            extra_params = {"from": int(incremental_cursor.timestamp())}

        async for batch in self._paginate_by_offset(
            url,
            data_key="host_list",
            offset_param="start",
            size_param="count",
            extra_params=extra_params,
        ):
            yield batch

    async def _hosts_edited_since(self, since: datetime) -> bool:
        async for _ in self._search_audit_events(
            HOST_EDITS_AUDIT_QUERY, since, page_size=1
        ):
            logger.info(
                f"Host tags or mutes were edited since {since.isoformat()}; "
                "listing every host"
            )
            return True
        return False
