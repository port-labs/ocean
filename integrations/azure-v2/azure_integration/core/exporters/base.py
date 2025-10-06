from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, List

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.client import AzureClient
from azure_integration.utils import turn_sequence_to_chunks


class BaseExporter(ABC):
    def __init__(self, client: AzureClient):
        self.client = client
        self.resource_config = event.resource_config

    async def export(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        subscription_batch_size = int(ocean.integration_config["subscription_batch_size"])
        all_subscriptions = await self.client.get_all_subscriptions()
        logger.info(f"Discovered {len(all_subscriptions)} subscriptions")

        if not all_subscriptions:
            logger.error("No subscriptions found in Azure, exiting")
            return

        for subscriptions in turn_sequence_to_chunks(
            all_subscriptions,
            subscription_batch_size,
        ):
            logger.info(f"Running full sync for {self.__class__.__name__}")
            async for items in self._sync_for_subscriptions(
                [str(s.subscription_id) for s in subscriptions]
            ):
                yield items
            logger.info(f"Completed full sync for {self.__class__.__name__}")

    @abstractmethod
    async def _sync_for_subscriptions(
        self, subscriptions: List[str]
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        ...
