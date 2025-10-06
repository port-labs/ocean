from typing import Any, AsyncGenerator, List, Optional, cast

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from azure_integration.clients.client import AzureClient
from azure_integration.models import ResourceGroupTagFilters
from azure_integration.utils import build_rg_tag_filter_clause
from integration import AzureResourceConfig

from .base import BaseExporter


class ResourcesExporter(BaseExporter):
    resource_config: AzureResourceConfig

    def __init__(self, client: AzureClient, resource_config: ResourceConfig):
        super().__init__(client, resource_config)

    def _build_full_sync_query(
        self,
        resource_types: list[str] | None = None,
        tag_filters: Optional[ResourceGroupTagFilters] = None,
    ) -> str:
        resource_filter_clause = ""
        if resource_types:
            lower_resource_types = [f"'{rt.lower()}'" for rt in resource_types]
            resource_types_filter = ", ".join(lower_resource_types)
            resource_filter_clause = f"| where type in~ ({resource_types_filter})"

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

    async def _sync_for_subscriptions(
        self, subscriptions: List[str]
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        resource_types = self.resource_config.selector.resource_types
        tag_filters = self.resource_config.selector.tags

        logger.info(
            "Running query for subscription batch with "
            f"{len(subscriptions)} subscriptions"
        )

        query = self._build_full_sync_query(resource_types, tag_filters)
        async for items in self.client.run_query(
            query,
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resources")
            if not items:
                logger.info("No resources found in this batch")
                continue
            yield items
