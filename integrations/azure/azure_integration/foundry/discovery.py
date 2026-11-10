from __future__ import annotations

from typing import Any

from azure_integration.foundry.core.exporters.project_exporter import (
    FoundryProject,
    ProjectExporter,
)


def _tags(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("tags")
    return raw if isinstance(raw, dict) else {}


def _project_from_exported_row(row: dict[str, Any]) -> FoundryProject:
    return FoundryProject(
        project_arm_id=str(row["id"]),
        project_name=str(row["name"]),
        endpoint=str(row["__foundryProjectEndpoint"]),
        account_arm_id=str(row["accountArmId"]),
        account_name=str(row["accountName"]),
        subscription_id=str(row["subscriptionId"]),
        resource_group_name=str(row["resourceGroupName"]),
        account_endpoint_host=str(row["accountEndpointHost"]),
        location=row.get("location"),
        tags=_tags(row),
    )


async def resolve_project_by_endpoint(endpoint: str) -> FoundryProject:
    """Find a discovered Foundry project by its data-plane endpoint URL."""
    target = endpoint.rstrip("/")
    async for batch in ProjectExporter().get_paginated_resources():
        for row in batch:
            if str(row.get("__foundryProjectEndpoint") or "").rstrip("/") == target:
                return _project_from_exported_row(row)
    raise ValueError(f"No discovered Foundry project matches endpoint {target}")


def clear_foundry_project_cache() -> None:
    """Project listing uses Ocean's event cache; nothing process-global to clear."""
