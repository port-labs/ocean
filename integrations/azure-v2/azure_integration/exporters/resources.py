from typing import Any, AsyncGenerator, List, cast

from ...integration import AzureResourceConfig, AzureResourceContainerConfig
from ..client import AzureClient
from ..services.resource_containers import ResourceContainers
from ..services.resources import Resources
from .base import BaseExporter


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
        container_tags = self.resource_config.selector.tags
        resources_syncer = Resources(self.client)
        async for resources in resources_syncer.sync(
            subscriptions,
            resource_types=resource_types,
            tag_filters=container_tags,
        ):
            yield resources
