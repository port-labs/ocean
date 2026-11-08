from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

_project_endpoint: ContextVar[str | None] = ContextVar(
    "foundry_project_endpoint", default=None
)
_project_arm_id: ContextVar[str | None] = ContextVar(
    "foundry_project_arm_id", default=None
)


@contextmanager
def project_endpoint_context(
    endpoint: str, *, project_arm_id: str | None = None
) -> Iterator[str]:
    normalized = endpoint.rstrip("/")
    endpoint_token = _project_endpoint.set(normalized)
    arm_token: object | None = None
    if project_arm_id:
        arm_token = _project_arm_id.set(project_arm_id)
    try:
        yield normalized
    finally:
        _project_endpoint.reset(endpoint_token)
        if arm_token is not None:
            _project_arm_id.reset(arm_token)


def get_project_endpoint() -> str:
    current = _project_endpoint.get()
    if current:
        return current
    raise ValueError(
        "Foundry project endpoint is not set. Discover projects via ARM or pass "
        "projectEndpoint on the action / set project_endpoint_context."
    )


def project_name_from_endpoint(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if "/projects/" not in normalized:
        raise ValueError(
            "project endpoint must include /projects/{projectName} for Port MCP "
            "and ARM project scope"
        )
    return normalized.split("/projects/")[-1].split("/")[0]


def enrich_with_project(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    try:
        enriched["__foundryProjectEndpoint"] = get_project_endpoint()
    except ValueError:
        pass
    arm_id = _project_arm_id.get()
    if arm_id:
        enriched["__foundryProjectId"] = arm_id
    return enriched
