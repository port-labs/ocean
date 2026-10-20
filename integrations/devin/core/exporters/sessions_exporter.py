import time
from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from clients import endpoints
from core.exporters.abstract_exporter import AbstractDevinExporter
from core.tracking.tags import MANAGED_TAG

SECONDS_PER_DAY = 24 * 60 * 60


def build_sessions_query(
    *,
    include_archived: bool,
    created_after_days: int | None,
    origins: list[str] | None,
    only_managed_by_port: bool,
    now: float | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if not include_archived:
        params["is_archived"] = False
    if created_after_days is not None:
        current = time.time() if now is None else now
        params["created_after"] = int(current - created_after_days * SECONDS_PER_DAY)
    if origins:
        params["origins"] = list(origins)
    if only_managed_by_port:
        params["tags"] = [MANAGED_TAG]
    return params


class SessionsExporter(AbstractDevinExporter):
    async def get_paginated_resources(  # type: ignore[override]
        self,
        *,
        include_archived: bool = False,
        created_after_days: int | None = 30,
        origins: list[str] | None = None,
        only_managed_by_port: bool = False,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = build_sessions_query(
            include_archived=include_archived,
            created_after_days=created_after_days,
            origins=origins,
            only_managed_by_port=only_managed_by_port,
        )
        async for page in self.client.paginate(endpoints.SESSIONS, params=params):
            yield page

    async def get_resource(self, resource_id: str) -> RAW_ITEM:
        return await self.client.send_api_request("GET", endpoints.session(resource_id))
