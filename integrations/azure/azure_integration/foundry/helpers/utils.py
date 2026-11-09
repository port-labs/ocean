from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from port_ocean.utils.time import convert_str_to_utc_datetime


def enrich_with_project(
    item: dict[str, Any],
    *,
    project_endpoint: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Attach Foundry project identity fields used by JQ mappings / relations."""
    enriched = dict(item)
    enriched["__foundryProjectEndpoint"] = project_endpoint.rstrip("/")
    if project_id:
        enriched["__foundryProjectId"] = project_id
    return enriched


def parse_foundry_timestamp(value: object) -> datetime | None:
    """Parse Foundry API timestamps (ISO strings or Unix epoch seconds)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.isdigit():
            return datetime.fromtimestamp(int(stripped), tz=UTC)
        try:
            return convert_str_to_utc_datetime(stripped)
        except ValueError:
            return None
    return None


def timestamp_to_iso(value: object) -> str | None:
    parsed = parse_foundry_timestamp(value)
    if parsed is not None:
        return parsed.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    if value is not None:
        return str(value)
    return None


def effective_conversation_cutoff(
    incremental_cursor: datetime | None,
    *,
    since_days: int | None,
) -> datetime | None:
    """Latest cutoff: incremental cursor and/or relative ``since`` window."""
    bounds: list[datetime] = []
    if incremental_cursor is not None:
        bounds.append(incremental_cursor)
    if since_days is not None:
        bounds.append(datetime.now(UTC) - timedelta(days=since_days))
    if not bounds:
        return None
    return max(bounds)
