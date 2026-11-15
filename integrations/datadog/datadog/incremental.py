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

# https://docs.datadoghq.com/account_management/audit_trail/events/#internal-developer-portal
# Deletes are excluded: the full resync reconciles removed services.
CHANGED_SERVICES_AUDIT_QUERY = (
    '@evt.name:"Internal Developer Portal" @asset.type:idp_entity '
    r"@action:(created OR modified) @asset.id:service\:*"
)


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


def audit_event_asset_id(event: dict[str, Any]) -> str | None:
    """Return the ID of the asset an audit event is about."""
    return event.get("attributes", {}).get("attributes", {}).get("asset", {}).get("id")


def service_name_from_ref(ref: str) -> str | None:
    """Return the service name in a catalog entity reference
    (``service:<namespace>/<name>``), or None for other entity kinds."""
    if not ref.startswith("service:"):
        return None
    return ref.partition("/")[2] or None
