from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from incident_io.clients.client import PAGE_SIZE, IncidentIoClient
from incident_io.core.exporters.abstract_exporter import AbstractIncidentIoExporter
from incident_io.core.options import IncidentOptions
from incident_io.helpers.exceptions import IncidentIoApiError
from incident_io.helpers.utils import safe_resource_id

INCIDENTS_ENDPOINT = "v2/incidents"
SEVERITIES_ENDPOINT = "v1/severities"
# Included only when the selector asks for test and tutorial incidents. The
# API otherwise returns standard and retrospective incidents.
INCIDENT_MODES_INCLUDING_TEST = ("standard", "retrospective", "test", "tutorial")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _api_date(value: datetime) -> str:
    # List filters accept yyyy-mm-dd. A timestamp is rejected.
    return _as_utc(value).strftime("%Y-%m-%d")


def build_incident_params(
    options: IncidentOptions,
    now: datetime,
    since: datetime | None = None,
    severity_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Incidents created in the selector window.

    A full resync filters on ``created_at``. An incremental run also filters
    on ``updated_at`` from the Ocean cursor, and still will not look further
    back than ``days_back``. Both filters are calendar dates, so an
    incremental run re-reads the cursor's UTC day.
    """
    end = _as_utc(now)
    window_start = end - timedelta(days=options["days_back"])
    params: dict[str, Any] = {"created_at[gte]": _api_date(window_start)}
    if since is not None:
        start = min(max(_as_utc(since), window_start), end)
        params["updated_at[gte]"] = _api_date(start)
    categories = options.get("status_categories")
    if categories:
        params["status_category[one_of]"] = list(categories)
    if options.get("include_test"):
        params["mode[one_of]"] = list(INCIDENT_MODES_INCLUDING_TEST)
    if severity_ids:
        params["severity[one_of]"] = list(severity_ids)
    return params


class IncidentExporter(AbstractIncidentIoExporter[IncidentIoClient]):
    async def _severity_ids(self, requested: list[str]) -> list[str]:
        """Resolve severity names or ids to the ids `severity[one_of]` expects."""
        by_key: dict[str, str] = {}
        names: list[str] = []
        async for page in self.client.send_paginated_request(
            SEVERITIES_ENDPOINT,
            data_key="severities",
            page_size=50,
        ):
            for item in page:
                severity_id = item.get("id")
                name = item.get("name")
                if not isinstance(severity_id, str) or not severity_id:
                    continue
                by_key.setdefault(severity_id, severity_id)
                if isinstance(name, str) and name.strip():
                    by_key.setdefault(name.strip().lower(), severity_id)
                    names.append(name.strip())
        resolved: list[str] = []
        missing: list[str] = []
        for value in requested:
            match = by_key.get(value) or by_key.get(value.lower())
            if match is None:
                missing.append(value)
            elif match not in resolved:
                resolved.append(match)
        if missing:
            known = ", ".join(names) or "none"
            raise IncidentIoApiError(
                f"Unknown severities: {missing}. This account has: {known}."
            )
        return resolved

    async def get_paginated_resources(
        self, options: IncidentOptions, since: datetime | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        requested = options.get("severities") or None
        severity_ids = await self._severity_ids(list(requested)) if requested else None
        params = build_incident_params(
            options, datetime.now(timezone.utc), since=since, severity_ids=severity_ids
        )
        async for incidents in self.client.send_paginated_request(
            INCIDENTS_ENDPOINT,
            data_key="incidents",
            params=params,
            page_size=PAGE_SIZE,
        ):
            yield incidents

    async def get_single_resource(
        self, resource_id: str, options: Any = None
    ) -> Optional[RAW_ITEM]:
        response = await self.client.send_api_request(
            f"{INCIDENTS_ENDPOINT}/{safe_resource_id(resource_id)}"
        )
        incident = response.get("incident")
        return incident if isinstance(incident, dict) else None
