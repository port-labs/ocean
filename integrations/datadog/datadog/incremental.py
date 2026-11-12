"""Incremental sync constants and helpers for Datadog."""

from datetime import datetime, timezone
from typing import Any

from datadog.utils import parse_restriction_policy_asset

# https://docs.datadoghq.com/account_management/audit_trail/events/#service-level-objectives
CHANGED_SLOS_AUDIT_QUERY = "@evt.name:SLO @asset.type:slo @action:(created OR modified)"

# https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
CHANGED_RESTRICTION_POLICIES_AUDIT_QUERY = (
    '@evt.name:"Access Management" @asset.type:restriction_policy '
    "@action:(modified OR deleted)"
)


def windows_ending_after(
    windows: list[tuple[int, int]], cursor: datetime
) -> list[tuple[int, int]]:
    """Keep the time windows that end after *cursor*: the current window, plus any
    window that closed since *cursor*, so it gets its final values."""
    cursor_ts = int(cursor.timestamp())
    return [(from_ts, to_ts) for from_ts, to_ts in windows if to_ts > cursor_ts]


def audit_events_search_body(query: str, cursor: datetime) -> dict[str, Any]:
    """Build an audit events search body for events matching *query* since *cursor*.
    Docs: https://docs.datadoghq.com/api/latest/audit/#search-audit-logs-events
    """
    return {
        "filter": {
            "query": query,
            "from": cursor.astimezone(timezone.utc).isoformat(),
            "to": "now",
        },
        "sort": "-timestamp",
    }


def audit_event_asset_id(event: dict[str, Any]) -> str | None:
    """Return the ID of the asset an audit event is about."""
    return event.get("attributes", {}).get("attributes", {}).get("asset", {}).get("id")


def restricted_resource_id(event: dict[str, Any], resource_type: str) -> str | None:
    """Return the ID of the *resource_type* resource whose restriction policy an audit
    event changed (its asset ID is ``<type>:<id>``), or None for other resource types.
    """
    asset = parse_restriction_policy_asset(audit_event_asset_id(event) or "")
    if asset and asset.type == resource_type:
        return asset.id
    return None
