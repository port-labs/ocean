from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

_project_endpoint: ContextVar[str | None] = ContextVar(
    "foundry_project_endpoint", default=None
)


@contextmanager
def project_endpoint_context(endpoint: str) -> Iterator[str]:
    normalized = endpoint.rstrip("/")
    token = _project_endpoint.set(normalized)
    try:
        yield normalized
    finally:
        _project_endpoint.reset(token)


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
        enriched["foundryProjectEndpoint"] = get_project_endpoint()
    except ValueError:
        pass
    return enriched
