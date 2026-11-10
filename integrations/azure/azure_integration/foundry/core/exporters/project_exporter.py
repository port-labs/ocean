from __future__ import annotations

import re
from typing import Any

from azure.identity.aio import DefaultAzureCredential
from azure.mgmt.resource.subscriptions.aio import SubscriptionClient
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_independent_async_iterators
from port_ocean.utils.cache import cache_iterator_result
from pydantic import BaseModel, ConfigDict, Field

from azure_integration.foundry.kinds import (
    DEFAULT_FOUNDRY_ARM_API_VERSION,
    FOUNDRY_ARM_PROJECT_KIND,
)
from azure_integration.iterators import resource_extention_kind_iterator
from azure_integration.utils import batch_resources_iterator

_ARM_PROJECT_ID = re.compile(
    r"^/subscriptions/(?P<sub>[^/]+)/resourceGroups/(?P<rg>[^/]+)"
    r"/providers/Microsoft\.CognitiveServices/accounts/(?P<account>[^/]+)"
    r"/projects/(?P<project>[^/]+)$",
    re.IGNORECASE,
)


class FoundryProject(BaseModel):
    model_config = ConfigDict(frozen=True, serialize_by_alias=True)

    project_arm_id: str = Field(serialization_alias="id")
    project_name: str = Field(serialization_alias="name")
    type: str = FOUNDRY_ARM_PROJECT_KIND
    location: str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)
    endpoint: str = Field(serialization_alias="__foundryProjectEndpoint")
    account_arm_id: str = Field(serialization_alias="accountArmId")
    account_name: str = Field(serialization_alias="accountName")
    subscription_id: str = Field(serialization_alias="subscriptionId")
    resource_group_name: str = Field(serialization_alias="resourceGroupName")
    account_endpoint_host: str = Field(serialization_alias="accountEndpointHost")

    @property
    def account_base_url(self) -> str:
        return f"https://{self.account_endpoint_host}"


def foundry_project_from_arm(project: dict[str, Any]) -> FoundryProject | None:
    project_id = str(project.get("id") or "")
    match = _ARM_PROJECT_ID.match(project_id)
    if match is None:
        return None

    subscription_id = match.group("sub")
    resource_group = match.group("rg")
    account_name = match.group("account")
    project_name = match.group("project")
    endpoint_host = f"{account_name}.services.ai.azure.com"
    location = project.get("location")
    raw_tags = project.get("tags")
    tags: dict[str, Any] = raw_tags if isinstance(raw_tags, dict) else {}
    return FoundryProject(
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        account_name=account_name,
        account_arm_id=(
            f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.CognitiveServices/accounts/{account_name}"
        ),
        project_name=project_name,
        project_arm_id=project_id,
        endpoint=f"https://{endpoint_host}/api/projects/{project_name}",
        account_endpoint_host=endpoint_host,
        location=str(location) if location else None,
        tags=tags,
    )


class ProjectExporter:
    @cache_iterator_result()
    async def get_paginated_resources(
        self,
        *,
        api_version: str = DEFAULT_FOUNDRY_ARM_API_VERSION,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        discovered = 0
        async with DefaultAzureCredential() as credential:
            async with SubscriptionClient(credential=credential) as subscription_client:
                async for subscriptions_batch in batch_resources_iterator(
                    subscription_client.subscriptions.list,
                ):
                    if not subscriptions_batch:
                        continue
                    tasks = [
                        resource_extention_kind_iterator(
                            credential=credential,
                            subscription_id=subscription["subscription_id"],
                            resource_kind=FOUNDRY_ARM_PROJECT_KIND,
                            api_version=api_version,
                        )
                        for subscription in subscriptions_batch
                    ]
                    async for batch in stream_independent_async_iterators(
                        *tasks, context="Foundry project exporter"
                    ):
                        projects = [
                            project.model_dump()
                            for raw in batch
                            if (project := foundry_project_from_arm(raw)) is not None
                        ]
                        if projects:
                            discovered += len(projects)
                            yield projects

        logger.info(f"Exported {discovered} Foundry project(s)")
