"""Incremental sync constants and helpers for Datadog."""

from datetime import datetime, timezone
from typing import Any

# Deletes are excluded on purpose: the full resync reconciles removed users.
# https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
CHANGED_USERS_AUDIT_QUERY = (
    '@evt.name:"Access Management" @asset.type:user @action:(created OR modified)'
)

# Role membership changes are audited on the roles API with the user as the asset.
# They're left to the role kind, which carries the membership.
ROLES_API_PATH_PREFIX = "/api/v2/roles"

# https://docs.datadoghq.com/account_management/audit_trail/events/#internal-developer-portal
# Deletes are excluded: the full resync reconciles removed services.
CHANGED_SERVICES_AUDIT_QUERY = (
    '@evt.name:"Internal Developer Portal" @asset.type:idp_entity '
    r"@action:(created OR modified) @asset.id:service\:*"
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


def audit_event_path(event: dict[str, Any]) -> str:
    """Return the API path of the request an audit event recorded, or "" if absent."""
    attributes = event.get("attributes", {}).get("attributes", {})
    return attributes.get("http", {}).get("url_details", {}).get("path", "")


def service_name_from_ref(ref: str) -> str | None:
    """Return the service name in a catalog entity reference
    (``service:<namespace>/<name>``), or None for other entity kinds."""
    if not ref.startswith("service:"):
        return None
    return ref.partition("/")[2] or None
