from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from coralogix.clients.client import CoralogixClient, PaginationStyle
from coralogix.core.exporters.abstract_exporter import AbstractCoralogixExporter
from coralogix.core.options import CaseOptions
from coralogix.helpers.utils import MGMT_API_PREFIX

CASES_ENDPOINT = f"{MGMT_API_PREFIX}/cases/cases/v1"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _case_timestamp(value: datetime) -> str:
    return _as_utc(value).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_case_filters(
    options: CaseOptions, now: datetime, since: datetime | None = None
) -> dict[str, Any]:
    """Cases created in the selector window.

    A full resync uses ``days_back``. An incremental run passes the Ocean
    cursor as ``since`` and still will not look further back than ``days_back``.
    """
    end = _as_utc(now)
    window_start = end - timedelta(days=options["days_back"])
    start = window_start
    if since is not None:
        start = min(max(_as_utc(since), window_start), end)
    filters: dict[str, Any] = {
        "dateRange": {
            "from": _case_timestamp(start),
            "to": _case_timestamp(end),
            "mode": "DATE_RANGE_MODE_CREATED_AT",
        }
    }
    if options.get("statuses"):
        filters["statuses"] = options["statuses"]
    return filters


class CaseExporter(AbstractCoralogixExporter[CoralogixClient]):
    async def get_paginated_resources(
        self, options: CaseOptions, since: datetime | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        team_url = await self.get_team_url()
        body = {
            "filters": build_case_filters(
                options, datetime.now(timezone.utc), since=since
            )
        }
        async for cases in self.client.send_paginated_request(
            CASES_ENDPOINT,
            data_key="cases",
            style=PaginationStyle.TOKEN_BODY,
            method="POST",
            json_data=body,
        ):
            yield self.with_team_url(cases, team_url)

    async def get_single_resource(
        self, resource_id: str, options: Any = None
    ) -> Optional[RAW_ITEM]:
        response = await self.client.send_api_request(f"{CASES_ENDPOINT}/{resource_id}")
        return response.get("case") or None
