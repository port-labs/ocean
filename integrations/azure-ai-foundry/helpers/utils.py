from __future__ import annotations

from datetime import UTC, datetime

from port_ocean.utils.time import convert_str_to_utc_datetime


def region_from_project_endpoint(project_endpoint: str) -> str | None:
    host = project_endpoint.split("//", maxsplit=1)[-1].split("/", maxsplit=1)[0]
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] == "api":
        return parts[-3]
    return None


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
