from typing import Any, AsyncGenerator, Optional
from loguru import logger

from azure_integration.client import AzureClient
from azure_integration.models import ResourceGroupTagFilters
from azure_integration.utils import build_rg_tag_filter_clause


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


class Resources:
    def __init__(self, azure_client: AzureClient):
        self.azure_client = azure_client

    # AI! update this method docs
    async def sync(
        self,
        subscriptions: list[str],
        resource_types: list[str] | None = None,
        tag_filters: Optional[ResourceGroupTagFilters] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Syncs resources from Azure for the given subscriptions.

        Args:
            subscriptions: A list of subscription IDs to sync resources from.
            resource_types: An optional list of resource types to filter by.

        Yields:
            A list of resources.
        """
        logger.info(
            "Running query for subscription batch with "
            f"{len(subscriptions)} subscriptions"
        )

        query = build_full_sync_query(resource_types, tag_filters)
        async for items in self.azure_client.run_query(
            query,
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resources")
            if not items:
                logger.info("No resources found in this batch")
                continue
            yield items
