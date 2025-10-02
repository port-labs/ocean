from typing import Any, AsyncGenerator, Optional

from loguru import logger
from azure_integration.client import AzureClient
from azure_integration.models import ResourceGroupTagFilters
from azure_integration.utils import build_rg_tag_filter_clause


def build_rg_query(rg_tag_filter: Optional[ResourceGroupTagFilters] = None) -> str:
    filters = build_rg_tag_filter_clause(rg_tag_filter) if rg_tag_filter else ""
    FULL_SYNC_QUERY: str = f"""
        resourcecontainers
        {filters}
        | extend resourceId=tolower(id)
        | project resourceId, type, name, location, tags, subscriptionId, resourceGroup
        | extend resourceGroup=tolower(resourceGroup)
        | extend type=tolower(type)
        """
    return FULL_SYNC_QUERY


class ResourceContainers:
    def __init__(self, azure_client: AzureClient):
        self.azure_client = azure_client

    async def sync_full(
        self, subscriptions: list[str], rg_tag_filter: Optional[ResourceGroupTagFilters]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(
            "Running query for subscription batch with "
            f"{len(subscriptions)} subscriptions"
        )

        async for items in self.azure_client.run_query(
            build_rg_query(rg_tag_filter),
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resource containers")
            if not items:
                logger.info("No resources found in this batch")
                continue
            yield items
