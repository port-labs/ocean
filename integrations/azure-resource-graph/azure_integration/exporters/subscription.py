from typing import AsyncGenerator, Dict, Any
from port_ocean.utils.cache import cache_iterator_result
from azure_integration.exporters.base import BaseExporter
from azure_integration.options import SubscriptionExporterOptions
from azure_integration.clients.base import AzureRequest


class SubscriptionExporter(BaseExporter):

    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: SubscriptionExporterOptions
    ) -> AsyncGenerator[list[Dict[str, Any]], None]:
        request = AzureRequest(
            endpoint="subscriptions",
            data_key="value",
            api_version=options.api_version,
        )
        async for subscriptions in self.client.make_paginated_request(request):
            yield subscriptions
