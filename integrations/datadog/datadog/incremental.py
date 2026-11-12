"""Incremental sync constants and helpers for Datadog."""

from datetime import datetime, timezone
from typing import Any

# Deletes are excluded on purpose: the full resync reconciles removed users.
# https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
CHANGED_USERS_AUDIT_QUERY = (
    '@evt.name:"Access Management" @asset.type:user @action:(created OR modified)'
)

# Role membership changes are audited on the roles API with the user as the asset;
# they don't change the user itself.
ROLES_API_PATH_PREFIX = "/api/v2/roles"


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


def changed_user_id(event: dict[str, Any]) -> str | None:
    """Return the ID of the user an audit event changed, or None for role membership events."""
    attributes = event.get("attributes", {}).get("attributes", {})
    path = attributes.get("http", {}).get("url_details", {}).get("path", "")
    if path.startswith(ROLES_API_PATH_PREFIX):
        return None
    return attributes.get("asset", {}).get("id")
