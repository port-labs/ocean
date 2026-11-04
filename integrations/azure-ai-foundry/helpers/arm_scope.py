from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from port_ocean.helpers.async_client import OceanAsyncClient

from clients.auth.factory import create_authenticator
from helpers.project_scope import get_project_endpoint

_MANAGEMENT_SCOPE = "https://management.azure.com/.default"
_SUBSCRIPTIONS_API = "2022-12-01"
_COGSERV_ACCOUNTS_API = "2025-06-01"
_ARM_ID_PATTERN = re.compile(
    r"^/subscriptions/(?P<sub>[^/]+)/resourceGroups/(?P<rg>[^/]+)"
    r"/providers/Microsoft\.CognitiveServices/accounts/(?P<account>[^/]+)"
)


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


_resolved_scope: ArmDeploymentScope | None = None
_resolve_lock = asyncio.Lock()


def clear_arm_scope_cache() -> None:
    global _resolved_scope
    _resolved_scope = None


def _config_value(config: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = config.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _scope_from_integration_config(config: dict[str, Any]) -> ArmDeploymentScope | None:
    """Build ARM scope from integration config (no subscription-wide account listing)."""
    subscription_id = _config_value(
        config, "azureSubscriptionId", "azure_subscription_id"
    )
    resource_group_name = _config_value(
        config, "azureResourceGroupName", "azure_resource_group_name"
    )
    if not subscription_id and not resource_group_name:
        return None
    if not subscription_id or not resource_group_name:
        raise ValueError(
            "Both azureSubscriptionId and azureResourceGroupName are required "
            "when either is set."
        )
    account_name = account_name_from_project_endpoint(get_project_endpoint())
    if not account_name:
        raise ValueError(
            "Could not parse Cognitive Services account name from foundryProjectEndpoint"
        )
    api_version = (
        _config_value(config, "arm_management_api_version", "armManagementApiVersion")
        or "2025-06-01"
    )
    logger.info(
        "Using configured Foundry ARM scope: "
        f"subscription={subscription_id}, resourceGroup={resource_group_name}, "
        f"account={account_name}"
    )
    return ArmDeploymentScope(
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        account_name=account_name,
        api_version=api_version,
    )


def account_name_from_project_endpoint(project_endpoint: str) -> str | None:
    hostname = urlparse(project_endpoint).hostname
    if not hostname:
        return None
    return hostname.split(".", maxsplit=1)[0] or None


def parse_cognitive_services_account_arm_id(
    resource_id: str,
) -> tuple[str, str, str] | None:
    match = _ARM_ID_PATTERN.match(resource_id)
    if not match:
        return None
    return match.group("sub"), match.group("rg"), match.group("account")


def _account_matches_endpoint_key(account: dict[str, Any], endpoint_key: str) -> bool:
    key = endpoint_key.lower()
    name = str(account.get("name") or "").lower()
    custom = str((account.get("properties") or {}).get("customSubDomainName") or "").lower()
    return name == key or custom == key


def _pick_account_matches(
    accounts: list[dict[str, Any]], endpoint_key: str
) -> list[dict[str, Any]]:
    return [item for item in accounts if _account_matches_endpoint_key(item, endpoint_key)]


async def _management_headers(config: dict[str, Any]) -> dict[str, str]:
    authenticator = create_authenticator(config)
    credential = getattr(authenticator, "_credential", None)
    if credential is None:
        return await authenticator.get_authorization_header()
    token = await credential.get_token(_MANAGEMENT_SCOPE)
    return {"Authorization": f"Bearer {token.token}"}


async def _list_enabled_subscription_ids(
    http: OceanAsyncClient, headers: dict[str, str]
) -> list[str]:
    response = await http.get(
        f"https://management.azure.com/subscriptions?api-version={_SUBSCRIPTIONS_API}",
        headers=headers,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return []
    values = payload.get("value")
    if not isinstance(values, list):
        return []
    ids: list[str] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        if item.get("state") != "Enabled":
            continue
        sub_id = item.get("subscriptionId")
        if isinstance(sub_id, str) and sub_id:
            ids.append(sub_id)
    return ids


async def discover_arm_scope_from_foundry_project(
    config: dict[str, Any],
) -> ArmDeploymentScope:
    """Resolve subscription + resource group by listing Cognitive Services accounts."""
    endpoint_key = account_name_from_project_endpoint(get_project_endpoint())
    if not endpoint_key:
        raise ValueError(
            "Could not parse Cognitive Services account name from foundryProjectEndpoint"
        )

    api_version = (
        _config_value(config, "arm_management_api_version", "armManagementApiVersion")
        or "2025-06-01"
    )
    http = OceanAsyncClient(timeout=httpx.Timeout(60.0))
    try:
        headers = await _management_headers(config)
        subscription_ids = await _list_enabled_subscription_ids(http, headers)

        matches: list[dict[str, Any]] = []
        for subscription_id in subscription_ids:
            list_url = (
                "https://management.azure.com/subscriptions/"
                f"{subscription_id}/providers/Microsoft.CognitiveServices/accounts"
                f"?api-version={_COGSERV_ACCOUNTS_API}"
            )
            response = await http.get(list_url, headers=headers)
            if response.status_code in {403, 404}:
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                continue
            value = payload.get("value")
            if not isinstance(value, list):
                continue
            accounts = [item for item in value if isinstance(item, dict)]
            matches.extend(_pick_account_matches(accounts, endpoint_key))

        if not matches:
            raise ValueError(
                f"No Cognitive Services account found for Foundry host '{endpoint_key}'. "
                "Grant Reader/list access on Cognitive Services accounts in your subscription(s)."
            )
        if len(matches) > 1:
            choices = ", ".join(
                f"{m.get('id')}"
                for m in matches[:5]
            )
            raise ValueError(
                f"Multiple Cognitive Services accounts match '{endpoint_key}': {choices}. "
                "Use a unique account subdomain or resolve the ambiguity in Azure."
            )

        parsed = parse_cognitive_services_account_arm_id(str(matches[0].get("id") or ""))
        if parsed is None:
            raise ValueError("Matched Cognitive Services account has an unexpected ARM id")
        subscription_id, resource_group_name, account_name = parsed
        logger.info(
            f"Resolved Foundry ARM scope from project endpoint: "
            f"subscription={subscription_id}, resourceGroup={resource_group_name}, "
            f"account={account_name}"
        )
        return ArmDeploymentScope(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            account_name=account_name,
            api_version=api_version,
        )
    finally:
        await http.aclose()


async def ensure_arm_deployment_scope(
    config: dict[str, Any] | None = None,
) -> ArmDeploymentScope:
    """Discover subscription + resource group from foundryProjectEndpoint (cached)."""
    from port_ocean.context.ocean import ocean

    global _resolved_scope

    merged = dict(ocean.integration_config)
    if config:
        merged.update(config)

    async with _resolve_lock:
        if _resolved_scope is not None:
            return _resolved_scope
        configured = _scope_from_integration_config(merged)
        if configured is not None:
            _resolved_scope = configured
            return _resolved_scope
        _resolved_scope = await discover_arm_scope_from_foundry_project(merged)
        return _resolved_scope


def get_arm_deployment_scope(config: dict[str, Any] | None = None) -> ArmDeploymentScope:
    if _resolved_scope is not None:
        return _resolved_scope

    account_name = account_name_from_project_endpoint(get_project_endpoint())
    raise ValueError(
        "ARM scope has not been resolved from the Foundry project yet. "
        f"(account from endpoint: {account_name or 'unknown'})"
    )
