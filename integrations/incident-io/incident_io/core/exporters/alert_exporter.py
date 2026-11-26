from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from incident_io.clients.client import IncidentIoClient
from incident_io.core.exporters.abstract_exporter import AbstractIncidentIoExporter
from incident_io.core.options import AlertOptions
from incident_io.helpers.utils import safe_resource_id

ALERTS_ENDPOINT = "v2/alerts"
# The list query rejects a page size above 50.
ALERT_PAGE_SIZE = 50


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_alert_params(
    options: AlertOptions,
    now: datetime,
    since: datetime | None = None,
) -> dict[str, Any]:
    """Alerts created in the selector window.

    ``created_at`` is a calendar date. ``updated_at`` accepts a timestamp, so
    an incremental run starts at the cursor instead of re-reading the whole
    UTC day. The cursor is still clamped inside ``days_back``.
    """
    end = _as_utc(now)
    window_start = end - timedelta(days=options["days_back"])
    params: dict[str, Any] = {"created_at[gte]": window_start.strftime("%Y-%m-%d")}
    if since is not None:
        start = min(max(_as_utc(since), window_start), end)
        params["updated_at[gte]"] = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    statuses = options.get("statuses")
    if statuses:
        params["status[one_of]"] = list(statuses)
    return params


class AlertExporter(AbstractIncidentIoExporter[IncidentIoClient]):
    async def get_paginated_resources(
        self, options: AlertOptions, since: datetime | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = build_alert_params(options, datetime.now(timezone.utc), since=since)
        async for alerts in self.client.send_paginated_request(
            ALERTS_ENDPOINT,
            data_key="alerts",
            params=params,
            page_size=ALERT_PAGE_SIZE,
        ):
            yield alerts

    async def get_single_resource(
        self, resource_id: str, options: Any = None
    ) -> Optional[RAW_ITEM]:
        response = await self.client.send_api_request(
            f"{ALERTS_ENDPOINT}/{safe_resource_id(resource_id)}"
        )
        alert = response.get("alert")
        return alert if isinstance(alert, dict) else None
