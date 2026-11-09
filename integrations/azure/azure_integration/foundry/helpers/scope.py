from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import urlparse

from loguru import logger

from azure_integration.foundry.discovery import resolve_project_by_endpoint

_DEFAULT_API_VERSION = "2025-06-01"
_scope_by_account: dict[str, "ArmDeploymentScope"] = {}

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
    arm_token: Token[str | None] | None = None
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
            "project endpoint must include /projects/{projectName} for ARM project scope"
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


@dataclass(frozen=True)
class ArmDeploymentScope:
    subscription_id: str
    resource_group_name: str
    account_name: str
    api_version: str

    def deployment_url(self, deployment_name: str) -> str:
        return (
            "https://management.azure.com/subscriptions/"
            f"{self.subscription_id}/resourceGroups/{self.resource_group_name}"
            "/providers/Microsoft.CognitiveServices/accounts/"
            f"{self.account_name}/deployments/{deployment_name}"
            f"?api-version={self.api_version}"
        )

    def project_connection_url(self, project_name: str, connection_name: str) -> str:
        return (
            "https://management.azure.com/subscriptions/"
            f"{self.subscription_id}/resourceGroups/{self.resource_group_name}"
            "/providers/Microsoft.CognitiveServices/accounts/"
            f"{self.account_name}/projects/{project_name}/connections/{connection_name}"
            f"?api-version={self.api_version}"
        )


def clear_arm_scope_cache() -> None:
    _scope_by_account.clear()


def account_name_from_project_endpoint(project_endpoint: str) -> str | None:
    hostname = urlparse(project_endpoint).hostname
    if not hostname:
        return None
    return hostname.split(".", maxsplit=1)[0] or None


async def ensure_arm_deployment_scope() -> ArmDeploymentScope:
    """Resolve ARM scope for the current Foundry project via discovery."""
    endpoint = get_project_endpoint()
    account_key = account_name_from_project_endpoint(endpoint) or endpoint
    cached = _scope_by_account.get(account_key)
    if cached is not None:
        return cached

    project = await resolve_project_by_endpoint(endpoint)
    scope = ArmDeploymentScope(
        subscription_id=project.subscription_id,
        resource_group_name=project.resource_group_name,
        account_name=project.account_name,
        api_version=_DEFAULT_API_VERSION,
    )
    _scope_by_account[account_key] = scope
    logger.info(
        "Resolved Foundry ARM scope: "
        f"subscription={scope.subscription_id}, resourceGroup={scope.resource_group_name}, "
        f"account={scope.account_name}"
    )
    return scope
