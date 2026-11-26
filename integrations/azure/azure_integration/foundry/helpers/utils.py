from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin

from port_ocean.utils.time import convert_str_to_utc_datetime

from azure_integration.foundry.models.agent import Agent, PromptAgentDefinition


def projects_matching_regions(
    projects: list[dict[str, Any]], regions: list[str]
) -> list[dict[str, Any]]:
    if not regions:
        return projects
    allowed = {r.casefold() for r in regions}
    return [
        project
        for project in projects
        if (project.get("location") or "").casefold() in allowed
    ]


def build_foundry_url(project_endpoint: str, path: str) -> str:
    base = project_endpoint.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def tools_from_agent_payload(agent: Any) -> list[Any]:
    if not isinstance(agent, dict) or "versions" not in agent:
        return []
    definition = Agent.model_validate(agent).latest_version.definition
    return definition.tools if isinstance(definition, PromptAgentDefinition) else []


def agent_openai_protocol_path(agent_id: str, resource: str) -> str:
    """Path under the agent OpenAI protocol endpoint (conversations/responses)."""
    return f"agents/{agent_id}/endpoint/protocols/openai/{resource}"


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into a shallow copy of base (dicts only).

    Overlay values override base at each key; nested dicts merge recursively.
    """
    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def project_name_from_endpoint(project_endpoint: str) -> str:
    """Last path segment of a Foundry project data-plane URL (``.../api/projects/<name>``)."""
    return project_endpoint.rstrip("/").rsplit("/", 1)[-1]


def enrich_with_project(
    item: dict[str, Any],
    *,
    project_endpoint: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Attach Foundry project identity fields used by JQ mappings / relations."""
    enriched = dict(item)
    enriched["__foundryProjectEndpoint"] = project_endpoint.rstrip("/")
    if project_id:
        enriched["__foundryProjectId"] = project_id
        enriched["__foundryProjectName"] = project_id.rstrip("/").rsplit("/", 1)[-1]
    else:
        # Mutations often only have the endpoint; deployment identifiers still need
        # ``.__foundryProjectName + "/" + .name`` (e.g. omby-project/gpt-4o-mini).
        enriched["__foundryProjectName"] = project_name_from_endpoint(project_endpoint)
    _coerce_created_at(enriched)
    versions = enriched.get("versions")
    if isinstance(versions, dict) and isinstance(versions.get("latest"), dict):
        latest = dict(versions["latest"])
        _coerce_created_at(latest)
        enriched["versions"] = {**versions, "latest": latest}
    return enriched


def parse_foundry_timestamp(value: object) -> datetime | None:
    """Parse Foundry API timestamps (ISO strings or Unix epoch seconds)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.isdigit():
            return datetime.fromtimestamp(int(stripped), tz=UTC)
        try:
            return convert_str_to_utc_datetime(stripped)
        except ValueError:
            return None
    return None


def timestamp_to_iso(value: object) -> str | None:
    """Normalize Foundry timestamps to RFC3339 UTC (`...Z`) for Port date-time."""
    parsed = parse_foundry_timestamp(value)
    if parsed is None:
        return None
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _coerce_created_at(item: dict[str, Any]) -> None:
    iso = timestamp_to_iso(item.get("created_at") or item.get("createdAt"))
    if iso is not None:
        item["created_at"] = iso


def invoke_scope_from_run(run: Any) -> tuple[str, str, str | None] | None:
    """Project endpoint, project id, optional agent id from an invoke run."""
    from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

    from azure_integration.foundry.core.exporters.project_exporter import (
        foundry_project_from_arm_id,
    )

    if not isinstance(run, IntegrationRun):
        return None
    props = run.output if isinstance(run, WorkflowNodeRun) else run.execution_properties
    project = foundry_project_from_arm_id(str(props.get("projectArmId") or ""))
    endpoint = (
        (project.endpoint if project else None)
        or props.get("projectEndpoint")
        or run.execution_properties.get("projectEndpoint")
    )
    if not isinstance(endpoint, str) or not endpoint.strip():
        return None
    agent_id = str(run.execution_properties.get("agentId") or "").strip() or None
    return endpoint.strip(), project_name_from_endpoint(endpoint), agent_id


def effective_conversation_cutoff(
    incremental_cursor: datetime | None,
    *,
    since_days: int | None,
) -> datetime | None:
    """Latest cutoff: incremental cursor and/or relative ``since`` window."""
    bounds: list[datetime] = []
    if incremental_cursor is not None:
        bounds.append(incremental_cursor)
    if since_days is not None:
        bounds.append(datetime.now(UTC) - timedelta(days=since_days))
    if not bounds:
        return None
    return max(bounds)
