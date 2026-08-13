from typing import Any

from port_ocean.utils.time import parse_interval_to_minutes


def read_app_spec_interval(integration: dict[str, Any], field: str) -> str | None:
    value = integration.get("spec", {}).get("appSpec", {}).get(field)
    if value is None:
        return None
    return str(value)


def resolve_app_spec_interval_minutes(
    integration: dict[str, Any],
    field: str,
    *,
    fallback_minutes: int,
) -> int:
    interval_str = read_app_spec_interval(integration, field)
    if interval_str:
        return parse_interval_to_minutes(interval_str)
    return fallback_minutes
