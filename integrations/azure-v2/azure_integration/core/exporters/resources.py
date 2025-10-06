from typing import Any, AsyncGenerator, List, Optional, cast

from loguru import logger

from ....integration import AzureResourceConfig, AzureResourceContainerConfig
from ...client import AzureClient
from ...models import ResourceGroupTagFilters
from ...services.resource_containers import ResourceContainers
from ...utils import build_rg_tag_filter_clause
from .base import BaseExporter


def build_full_sync_query(
    resource_types: list[str] | None = None,
    tag_filters: Optional[ResourceGroupTagFilters] = None,
) -> str:
    resource_filter_clause = ""
    if resource_types:
        resource_types_filter = " or ".join(
            [f"type == '{rt}'" for rt in resource_types]
        )
        resource_filter_clause = f"| where {resource_types_filter}"

    rg_tag_filter_clause = (
        build_rg_tag_filter_clause(tag_filters, tag_key_name="rgTags")
        if tag_filters
        else ""
    )
    query = f"""
    resources
    | project id, type, name, location, tags, subscriptionId, resourceGroup
    | extend resourceGroup=tolower(resourceGroup)
    | extend type=tolower(type)
    {resource_filter_clause}
    | join kind=leftouter (
        resourcecontainers
        | where type =~ 'microsoft.resources/subscriptions/resourcegroups'
        | project rgName=tolower(name), rgTags=tags, rgSubscriptionId=subscriptionId
    ) on $left.subscriptionId == $right.rgSubscriptionId and $left.resourceGroup == $right.rgName
    {rg_tag_filter_clause}
    | project id, type, name, location, tags, subscriptionId, resourceGroup, rgTags
    """

    return query


class ResourceContainersExporter(BaseExporter):
    def __init__(self, client: AzureClient):
        super().__init__(client)
        self.resource_config = cast(
            AzureResourceContainerConfig, self.resource_config
        )

    async def _sync_for_subscriptions(
        self, subscriptions: List[str]
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        container_tags = self.resource_config.selector.tags
        resource_containers_syncer = ResourceContainers(self.client)
        async for resource_containers in resource_containers_syncer.sync(
            subscriptions,
            rg_tag_filter=container_tags,
        ):
            yield resource_containers


class ResourcesExporter(BaseExporter):
    def __init__(self, client: AzureClient):
        super().__init__(client)
        self.resource_config = cast(AzureResourceConfig, self.resource_config)

    async def _sync_for_subscriptions(
        self, subscriptions: List[str]
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        resource_types = self.resource_config.selector.resource_types
        tag_filters = self.resource_config.selector.tags

        logger.info(
            "Running query for subscription batch with "
            f"{len(subscriptions)} subscriptions"
        )

        query = build_full_sync_query(resource_types, tag_filters)
        async for items in self.client.run_query(
            query,
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resources")
            if not items:
                logger.info("No resources found in this batch")
                continue
            yield items
