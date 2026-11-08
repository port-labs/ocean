from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.clients.auth.factory import create_authenticator

_MANAGEMENT_SCOPE = "https://management.azure.com/.default"
_SUBSCRIPTIONS_API = "2022-12-01"
_COGSERV_API = "2025-06-01"
_ARM_ACCOUNT_ID = re.compile(
    r"^/subscriptions/(?P<sub>[^/]+)/resourceGroups/(?P<rg>[^/]+)"
    r"/providers/Microsoft\.CognitiveServices/accounts/(?P<account>[^/]+)"
)

_cache: list["FoundryProject"] | None = None
_cache_lock = asyncio.Lock()


@dataclass(frozen=True)
class FoundryProject:
    subscription_id: str
    resource_group_name: str
    account_name: str
    account_arm_id: str
    project_name: str
    project_arm_id: str
    endpoint: str
    account_endpoint_host: str
    location: str | None = None
    tags: dict[str, Any] | None = None

    @property
    def account_base_url(self) -> str:
        return f"https://{self.account_endpoint_host}"


def clear_foundry_project_cache() -> None:
    global _cache
    _cache = None


def _parse_account_id(resource_id: str) -> tuple[str, str, str] | None:
    match = _ARM_ACCOUNT_ID.match(resource_id)
    if not match:
        return None
    return match.group("sub"), match.group("rg"), match.group("account")


def _account_host(account: dict[str, Any]) -> str | None:
    props = account.get("properties") if isinstance(account.get("properties"), dict) else {}
    custom = props.get("customSubDomainName") if isinstance(props, dict) else None
    name = account.get("name")
    host_key = str(custom or name or "").strip()
    if not host_key:
        return None
    # Data-plane APIs use *.services.ai.azure.com, not *.cognitiveservices.azure.com.
    return f"{host_key}.services.ai.azure.com"


def _data_plane_project_name(arm_project_name: str) -> str:
    """ARM may return ``account/project``; Foundry URLs use the project segment only."""
    segment = arm_project_name.strip().strip("/")
    if "/" in segment:
        return segment.rsplit("/", 1)[-1]
    return segment


def _endpoint_from_project_properties(project: dict[str, Any]) -> str | None:
    props = project.get("properties") if isinstance(project.get("properties"), dict) else {}
    endpoint = props.get("endpoint") if isinstance(props, dict) else None
    if not isinstance(endpoint, str) or not endpoint.strip():
        return None
    parsed = urlparse(endpoint.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    path = parsed.path.rstrip("/")
    if not path.startswith("/api/projects/"):
        return None
    host = parsed.hostname
    if host and host.endswith(".cognitiveservices.azure.com"):
        subdomain = host.removesuffix(".cognitiveservices.azure.com")
        host = f"{subdomain}.services.ai.azure.com"
    return f"{parsed.scheme}://{host}{path}"


async def _management_headers() -> dict[str, str]:
    authenticator = create_authenticator(dict(ocean.integration_config))
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
    values = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(values, list):
        return []
    ids: list[str] = []
    for item in values:
        if not isinstance(item, dict) or item.get("state") != "Enabled":
            continue
        sub_id = item.get("subscriptionId")
        if isinstance(sub_id, str) and sub_id:
            ids.append(sub_id)
    return ids


async def _list_accounts(
    http: OceanAsyncClient, headers: dict[str, str], subscription_id: str
) -> list[dict[str, Any]]:
    url = (
        "https://management.azure.com/subscriptions/"
        f"{subscription_id}/providers/Microsoft.CognitiveServices/accounts"
        f"?api-version={_COGSERV_API}"
    )
    response = await http.get(url, headers=headers)
    if response.status_code in {403, 404}:
        logger.debug(
            f"Skipping Cognitive Services list for subscription {subscription_id}: "
            f"{response.status_code}"
        )
        return []
    response.raise_for_status()
    payload = response.json()
    values = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict)]


async def _list_projects(
    http: OceanAsyncClient,
    headers: dict[str, str],
    subscription_id: str,
    resource_group: str,
    account_name: str,
) -> list[dict[str, Any]]:
    url = (
        "https://management.azure.com/subscriptions/"
        f"{subscription_id}/resourceGroups/{resource_group}/providers/"
        f"Microsoft.CognitiveServices/accounts/{account_name}/projects"
        f"?api-version={_COGSERV_API}"
    )
    response = await http.get(url, headers=headers)
    if response.status_code in {403, 404}:
        logger.debug(
            f"Skipping projects for account {account_name}: {response.status_code}"
        )
        return []
    response.raise_for_status()
    payload = response.json()
    values = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict)]


def _project_from_arm(
    account: dict[str, Any], project: dict[str, Any]
) -> FoundryProject | None:
    account_id = str(account.get("id") or "")
    parsed = _parse_account_id(account_id)
    if parsed is None:
        return None
    subscription_id, resource_group, account_name = parsed
    host = _account_host(account)
    arm_project_name = str(project.get("name") or "").strip()
    project_name = _data_plane_project_name(arm_project_name)
    if not host or not project_name:
        return None
    project_id = str(project.get("id") or f"{account_id}/projects/{arm_project_name}")
    endpoint = _endpoint_from_project_properties(project) or (
        f"https://{host}/api/projects/{project_name}"
    )
    endpoint_host = urlparse(endpoint).hostname or host
    tags = project.get("tags") if isinstance(project.get("tags"), dict) else account.get("tags")
    location = project.get("location") or account.get("location")
    return FoundryProject(
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        account_name=account_name,
        account_arm_id=account_id,
        project_name=project_name,
        project_arm_id=project_id,
        endpoint=endpoint,
        account_endpoint_host=endpoint_host,
        location=str(location) if location else None,
        tags=tags if isinstance(tags, dict) else None,
    )


async def discover_foundry_projects(*, force_refresh: bool = False) -> list[FoundryProject]:
    global _cache
    async with _cache_lock:
        if _cache is not None and not force_refresh:
            return list(_cache)

        http = OceanAsyncClient(timeout=httpx.Timeout(60.0))
        projects: list[FoundryProject] = []
        try:
            headers = await _management_headers()
            subscription_ids = await _list_enabled_subscription_ids(http, headers)
            logger.info(
                f"Discovering Foundry projects across {len(subscription_ids)} subscription(s)"
            )
            for subscription_id in subscription_ids:
                accounts = await _list_accounts(http, headers, subscription_id)
                for account in accounts:
                    parsed = _parse_account_id(str(account.get("id") or ""))
                    if parsed is None:
                        continue
                    _, resource_group, account_name = parsed
                    for project in await _list_projects(
                        http, headers, subscription_id, resource_group, account_name
                    ):
                        found = _project_from_arm(account, project)
                        if found is not None:
                            projects.append(found)
        except httpx.HTTPError as error:
            logger.error(f"Foundry project discovery failed: {error}")
            raise
        finally:
            await http.aclose()

        _cache = projects
        logger.info(f"Discovered {len(projects)} Foundry project(s)")
        return list(projects)


def foundry_project_to_raw(project: FoundryProject) -> dict[str, Any]:
    return {
        "id": project.project_arm_id,
        "name": project.project_name,
        "type": "Microsoft.CognitiveServices/accounts/projects",
        "location": project.location,
        "tags": project.tags or {},
        "foundryProjectEndpoint": project.endpoint,
        "accountArmId": project.account_arm_id,
        "accountName": project.account_name,
        "subscriptionId": project.subscription_id,
        "resourceGroupName": project.resource_group_name,
        "accountEndpointHost": project.account_endpoint_host,
    }


async def resolve_project_by_endpoint(endpoint: str) -> FoundryProject:
    normalized = endpoint.rstrip("/")
    for project in await discover_foundry_projects():
        if project.endpoint == normalized:
            return project
    raise ValueError(f"No discovered Foundry project matches endpoint {normalized}")
