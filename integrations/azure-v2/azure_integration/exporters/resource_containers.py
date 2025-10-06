from typing import Any, AsyncGenerator, Optional, cast

from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from azure_integration.clients.client import AzureClient
from azure_integration.models import ResourceGroupTagFilters
from azure_integration.utils import build_rg_tag_filter_clause
from integration import AzureResourceContainerConfig

from .base import BaseExporter


class ResourceContainersExporter(BaseExporter):
    resource_config: AzureResourceContainerConfig

    def __init__(self, client: AzureClient, resource_config: ResourceConfig):
        super().__init__(client, resource_config)

    def _build_sync_query(
        self, tag_filters: Optional[ResourceGroupTagFilters] = None
    ) -> str:
        rg_tag_filter_clause = (
            build_rg_tag_filter_clause(tag_filters) if tag_filters else ""
        )
        query: str = f"""
        resourcecontainers
        | where type =~ 'microsoft.resources/subscriptions/resourcegroups'
        {rg_tag_filter_clause}
        | project id, type, name, location, tags, subscriptionId, resourceGroup
        | extend resourceGroup=tolower(resourceGroup)
        | extend type=tolower(type)
        """
        return query

    async def _sync_for_subscriptions(
        self, subscriptions: list[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        container_tags = self.resource_config.selector.tags
        query = self._build_sync_query(container_tags)
        async for resource_containers in self.client.run_query(query, subscriptions):
            yield resource_containers
