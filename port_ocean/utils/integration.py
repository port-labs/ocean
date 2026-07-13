"""Utilities for reading integration spec/config values from the Port API response."""

from __future__ import annotations

from typing import Any

from loguru import logger

from port_ocean.utils.time import parse_interval_to_minutes


def read_app_spec_interval(integration: dict[str, Any], key: str) -> str | None:
    """Read a spec-level interval value from the integration object.

    Looks in integration["config"][key] first (portal-configured overrides),
    then integration["spec"]["appSpec"][key] (app spec defaults).
    Returns the raw string value or None if not found.
    """
    config_value = integration.get("config", {}).get(key)
    if config_value:
        return str(config_value)

    spec_value = integration.get("spec", {}).get("appSpec", {}).get(key)
    if spec_value:
        return str(spec_value)

    return None


def resolve_app_spec_interval_minutes(
    integration: dict[str, Any],
    key: str,
    *,
    fallback_minutes: int = 15,
) -> int:
    """Resolve an interval key from integration config/spec to minutes.

    Falls back to ``fallback_minutes`` when the key is not found or cannot be parsed.
    """
    raw = read_app_spec_interval(integration, key)
    if raw is None:
        logger.debug(
            f"Interval key '{key}' not found in integration config/spec, using fallback",
            fallback_minutes=fallback_minutes,
        )
        return fallback_minutes

    try:
        return parse_interval_to_minutes(raw)
    except Exception:
        logger.warning(
            f"Failed to parse interval '{raw}' for key '{key}', using fallback",
            fallback_minutes=fallback_minutes,
        )
        return fallback_minutes
