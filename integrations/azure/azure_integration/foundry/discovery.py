from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

from azure.core.exceptions import HttpResponseError
from azure.identity.aio import DefaultAzureCredential
from azure.mgmt.resource.subscriptions.aio import SubscriptionClient
from loguru import logger
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.utils.cache import cache_iterator_result

from azure_integration.foundry.kinds import FOUNDRY_ARM_PROJECT_KIND
from azure_integration.iterators import resource_extention_kind_iterator
from azure_integration.utils import batch_resources_iterator

_COGSERV_API = "2025-06-01"
_ARM_PROJECT_ID = re.compile(
    r"^/subscriptions/(?P<sub>[^/]+)/resourceGroups/(?P<rg>[^/]+)"
    r"/providers/Microsoft\.CognitiveServices/accounts/(?P<account>[^/]+)"
    r"/projects/(?P<project>[^/]+)$",
    re.IGNORECASE,
)


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


def _endpoint_from_project_properties(project: dict[str, Any]) -> str | None:
    props = project.get("properties")
    if not isinstance(props, dict):
        return None
    endpoint = props.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint.strip():
        return None
    parsed = urlparse(endpoint.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    path = parsed.path.rstrip("/")
    if not path.startswith("/api/projects/"):
        return None
    host = parsed.hostname
    if host.endswith(".cognitiveservices.azure.com"):
        subdomain = host.removesuffix(".cognitiveservices.azure.com")
        host = f"{subdomain}.services.ai.azure.com"
    return f"{parsed.scheme}://{host}{path}"


def foundry_project_from_arm(project: dict[str, Any]) -> FoundryProject | None:
    project_id = str(project.get("id") or "")
    match = _ARM_PROJECT_ID.match(project_id)
    if match is None:
        return None

    subscription_id = match.group("sub")
    resource_group = match.group("rg")
    account_name = match.group("account")
    project_name = match.group("project")

    account_arm_id = (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.CognitiveServices/accounts/{account_name}"
    )
    endpoint = _endpoint_from_project_properties(project) or (
        f"https://{account_name}.services.ai.azure.com/api/projects/{project_name}"
    )
    endpoint_host = (
        urlparse(endpoint).hostname or f"{account_name}.services.ai.azure.com"
    )
    tags = project.get("tags") if isinstance(project.get("tags"), dict) else None
    location = project.get("location")
    return FoundryProject(
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        account_name=account_name,
        account_arm_id=account_arm_id,
        project_name=project_name,
        project_arm_id=project_id,
        endpoint=endpoint,
        account_endpoint_host=endpoint_host,
        location=str(location) if location else None,
        tags=tags,
    )


async def _projects_for_subscription(
    credential: DefaultAzureCredential, subscription_id: str
) -> AsyncIterator[list[dict[str, Any]]]:
    try:
        async for batch in resource_extention_kind_iterator(
            credential=credential,
            subscription_id=subscription_id,
            resource_kind=FOUNDRY_ARM_PROJECT_KIND,
            api_version=_COGSERV_API,
        ):
            yield batch
    except HttpResponseError as error:
        if error.status_code in {403, 404}:
            logger.debug(
                f"Skipping Foundry discovery for subscription {subscription_id}: "
                f"{error.status_code}"
            )
            return
        raise


async def _discover_foundry_project_batches() -> AsyncIterator[list[FoundryProject]]:
    discovered = 0
    async with DefaultAzureCredential() as credential:
        async with SubscriptionClient(credential=credential) as subscription_client:
            async for subscriptions_batch in batch_resources_iterator(
                subscription_client.subscriptions.list,
            ):
                if not subscriptions_batch:
                    continue
                tasks = [
                    _projects_for_subscription(
                        credential, subscription["subscription_id"]
                    )
                    for subscription in subscriptions_batch
                ]
                async for batch in stream_async_iterators_tasks(*tasks):
                    projects: list[FoundryProject] = []
                    for raw in batch or []:
                        found = foundry_project_from_arm(raw)
                        if found is not None:
                            projects.append(found)
                    if projects:
                        discovered += len(projects)
                        yield projects

    logger.info(f"Discovered {discovered} Foundry project(s)")


@cache_iterator_result()
async def discover_foundry_projects() -> AsyncIterator[list[FoundryProject]]:
    async for batch in _discover_foundry_project_batches():
        yield batch


def foundry_project_to_raw(project: FoundryProject) -> dict[str, Any]:
    return {
        "id": project.project_arm_id,
        "name": project.project_name,
        "type": FOUNDRY_ARM_PROJECT_KIND,
        "location": project.location,
        "tags": project.tags or {},
        "__foundryProjectEndpoint": project.endpoint,
        "accountArmId": project.account_arm_id,
        "accountName": project.account_name,
        "subscriptionId": project.subscription_id,
        "resourceGroupName": project.resource_group_name,
        "accountEndpointHost": project.account_endpoint_host,
    }


async def resolve_project_by_endpoint(endpoint: str) -> FoundryProject:
    normalized = endpoint.rstrip("/")
    async for batch in discover_foundry_projects():
        for project in batch:
            if project.endpoint == normalized:
                return project
    raise ValueError(f"No discovered Foundry project matches endpoint {normalized}")
