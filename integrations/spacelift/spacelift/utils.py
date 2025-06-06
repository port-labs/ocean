"""Utility constants and helper functions for Spacelift integration."""

from enum import Enum


class ResourceKind(str, Enum):
    """Spacelift resource kinds."""

    SPACE = "space"
    STACK = "stack"
    DEPLOYMENT = "deployment"  # tracked runs
    POLICY = "policy"
    USER = "user"


def normalize_spacelift_resource(resource: dict, resource_type: str) -> dict:
    """Normalize Spacelift resource data for consistent processing.

    Args:
        resource: Raw resource data from Spacelift API
        resource_type: Type of the resource

    Returns:
        Normalized resource data
    """
    # Ensure consistent field naming
    normalized = resource.copy()

    # Add resource type metadata
    normalized["__resource_type"] = resource_type

    # Normalize timestamps
    timestamp_fields = ["createdAt", "updatedAt", "lastSeenAt"]
    for field in timestamp_fields:
        if field in normalized and normalized[field]:
            # Spacelift timestamps are typically Unix timestamps
            if isinstance(normalized[field], (int, float)):
                normalized[field] = int(normalized[field])

    # Normalize labels to always be a list
    if "labels" in normalized:
        if normalized["labels"] is None:
            normalized["labels"] = []
        elif isinstance(normalized["labels"], str):
            normalized["labels"] = [normalized["labels"]]

    return normalized


def get_resource_url(resource: dict, account_name: str) -> str:
    """Generate URL for a Spacelift resource.

    Args:
        resource: Resource data
        account_name: Spacelift account name

    Returns:
        URL to the resource in Spacelift UI
    """
    base_url = f"https://{account_name}.app.spacelift.io"

    resource_type = resource.get("__resource_type", "")
    resource_id = resource.get("id", "")

    if resource_type == ResourceKind.SPACE:
        return f"{base_url}/spaces/{resource_id}"
    elif resource_type == ResourceKind.STACK:
        return f"{base_url}/stack/{resource_id}"
    elif resource_type == ResourceKind.DEPLOYMENT:
        stack_id = resource.get("stack", {}).get("id", "")
        return f"{base_url}/stack/{stack_id}/run/{resource_id}"
    elif resource_type == ResourceKind.POLICY:
        return f"{base_url}/policy/{resource_id}"
    elif resource_type == ResourceKind.USER:
        return f"{base_url}/users"

    return base_url
