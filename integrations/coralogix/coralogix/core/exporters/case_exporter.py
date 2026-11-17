from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from coralogix.clients.client import CoralogixClient, PaginationStyle
from coralogix.core.exporters.abstract_exporter import AbstractCoralogixExporter
from coralogix.core.options import CaseOptions
from coralogix.helpers.utils import MGMT_API_PREFIX, IgnoredError

CASES_ENDPOINT = f"{MGMT_API_PREFIX}/cases/cases/v1"


def build_case_filters(options: CaseOptions, now: datetime) -> dict[str, Any]:
    since = now - timedelta(days=options["days_back"])
    filters: dict[str, Any] = {
        "dateRange": {
            "from": since.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "mode": "DATE_RANGE_MODE_CREATED_AT",
        }
    }
    if options.get("statuses"):
        filters["statuses"] = options["statuses"]
    return filters


class CaseExporter(AbstractCoralogixExporter[CoralogixClient]):
    async def get_paginated_resources(
        self, options: CaseOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        team_url = await self.get_team_url()
        body = {"filters": build_case_filters(options, datetime.now(timezone.utc))}
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
        response = await self.client.send_api_request(
            f"{CASES_ENDPOINT}/{resource_id}",
            ignored_errors=[IgnoredError(status=404, message="resource not found")],
        )
        return response.get("case") or None
