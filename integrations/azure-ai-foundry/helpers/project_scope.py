from __future__ import annotations

from typing import Any

from port_ocean.context.ocean import ocean


def get_project_endpoint() -> str:
    config: dict[str, Any] = ocean.integration_config
    endpoint = config.get("foundry_project_endpoint") or config.get(
        "foundryProjectEndpoint"
    )
    if not endpoint:
        raise ValueError(
            "foundryProjectEndpoint is required in the integration configuration"
        )
    return str(endpoint).rstrip("/")


def project_name_from_endpoint(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if "/projects/" not in normalized:
        raise ValueError(
            "foundryProjectEndpoint must include /projects/{projectName} for observability metrics"
        )
    return normalized.split("/projects/")[-1].split("/")[0]


def enrich_with_project(item: dict[str, Any]) -> dict[str, Any]:
    """Pass-through for raw catalog items. Project scope lives in integration config only."""
    return dict(item)
