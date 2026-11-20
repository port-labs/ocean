from enum import StrEnum
from urllib.parse import urlparse

DEFAULT_API_URL = "https://api.incident.io"
PERMISSIONS_DOCS_URL = "https://docs.incident.io/api-reference"

# Prefixes documented on the list endpoints. The incidents list reference does
# not name a scope; a 403 on that path still points at the API key settings.
REQUIRED_SCOPES: dict[str, str] = {
    "v2/users": "users.view",
    "v3/teams": "catalog_entries.view",
    "v2/schedules": "schedules.view",
}


class ObjectKind(StrEnum):
    INCIDENT = "incident"
    USER = "user"
    TEAM = "team"
    SCHEDULE = "schedule"


def required_permission(endpoint: str) -> str | None:
    endpoint = endpoint.lstrip("/")
    for prefix, scope in sorted(
        REQUIRED_SCOPES.items(), key=lambda item: -len(item[0])
    ):
        if endpoint == prefix or endpoint.startswith(f"{prefix}/"):
            return scope
    return None


def resolve_api_base_url(url: str | None) -> str:
    """Return an https origin for the incident.io API."""
    text = (url or "").strip() or DEFAULT_API_URL
    parsed = urlparse(text if "://" in text else f"https://{text}")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ValueError(
            f"incidentIoApiUrl must be an https URL such as {DEFAULT_API_URL}."
        )
    return f"https://{host}"


def safe_resource_id(resource_id: str) -> str:
    """Reject ids that would change the request path."""
    if (
        not isinstance(resource_id, str)
        or not resource_id
        or resource_id.strip() != resource_id
    ):
        raise ValueError("incident.io resource id is empty or padded with whitespace.")
    if resource_id in {".", ".."} or any(char in resource_id for char in "/?#\\"):
        raise ValueError("incident.io resource id contains an invalid character.")
    return resource_id
