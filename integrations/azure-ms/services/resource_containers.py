from typing import Any, AsyncGenerator

from loguru import logger
from clients.azure_client import AzureClient

FULL_SYNC_QUERY: str = """
resourcecontainers
| extend resourceId=tolower(id)
| project resourceId, type, name, location, tags, subscriptionId, resourceGroup
| extend resourceGroup=tolower(resourceGroup)
| extend type=tolower(type)
"""


class ResourceContainers:

    def __init__(self, azure_client: AzureClient):
        self.azure_client = azure_client

    async def sync_full(
        self,
        subscriptions: list[str],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(
            "Running query for subscription batch with "
            f"{len(subscriptions)} subscriptions"
        )

        async for items in self.azure_client.run_query(
            FULL_SYNC_QUERY,
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resource containers")
            if not items:
                logger.info("No resources found in this batch")
                continue
            yield items
