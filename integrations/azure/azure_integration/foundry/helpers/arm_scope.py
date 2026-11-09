from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from loguru import logger

from azure_integration.foundry.discovery import resolve_project_by_endpoint
from azure_integration.foundry.helpers.project_scope import get_project_endpoint

_DEFAULT_API_VERSION = "2025-06-01"
_scope_by_account: dict[str, "ArmDeploymentScope"] = {}


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
