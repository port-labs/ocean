from typing import Any, AsyncGenerator
from loguru import logger

from azure_integration.client import AzureClient


def build_full_sync_query(resource_types: list[str] | None = None) -> str:
    filter_clause = ""
    if resource_types:
        resource_types_filter = " or ".join(
            [f"type == '{rt}'" for rt in resource_types]
        )
        filter_clause = f"| where {resource_types_filter}"

    query = f"""
    resources
    {filter_clause}
    | extend resourceId=tolower(id)
    | extend resourceGroup=tolower(resourceGroup)
    | extend type=tolower(type)
    | project id, type, name, location, tags, subscriptionId, resourceGroup
    """

    return query


class Resources:
    def __init__(self, azure_client: AzureClient):
        self.azure_client = azure_client

    async def sync(
        self,
        subscriptions: list[str],
        resource_types: list[str] | None = None,
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

        query = build_full_sync_query(resource_types)
        async for items in self.azure_client.run_query(
            query,
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resources")
            if not items:
                logger.info("No resources found in this batch")
                continue
            print(items)
            yield items
