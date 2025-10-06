from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, List

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.clients.client import AzureClient
from azure_integration.utils import turn_sequence_to_chunks


class BaseExporter(ABC):
    def __init__(self, client: AzureClient, resource_config: ResourceConfig):
        self.client = client
        self.resource_config = resource_config

    async def export_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        subscription_batch_size = int(
            ocean.integration_config["subscription_batch_size"]
        )
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
    def _sync_for_subscriptions(
        self, subscriptions: List[str]
    ) -> AsyncGenerator[List[dict[str, Any]], None]: ...
