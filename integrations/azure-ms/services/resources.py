from typing import Any, AsyncGenerator
from loguru import logger

from clients.azure_client import AzureClient


def build_full_sync_query(resource_types: list[str] | None = None) -> str:
    filter_clause = ""
    if resource_types:
        resource_types_filter = " or ".join(
            [f"type == '{rt}'" for rt in resource_types]
        )
        filter_clause = f"| where {resource_types_filter}"

    query = f"""
    resources
    | extend resourceId=tolower(id)
    | project resourceId, type, name, location, tags, subscriptionId, resourceGroup
    | extend resourceGroup=tolower(resourceGroup)
    | extend type=tolower(type)
    {filter_clause}
    """

    return query


class Resources:
    def __init__(self, azure_client: AzureClient):
        self.azure_client = azure_client

    async def sync_full(
        self,
        subscriptions: list[str],
        resource_types: list[str] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(
            "Running query for subscription batch with "
            f"{len(subscriptions)} subscriptions"
        )

        async for items in self.azure_client.run_query(
            build_full_sync_query(resource_types),
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resources")
            if not items:
                logger.info("No resources found in this batch")
                continue
            yield items
