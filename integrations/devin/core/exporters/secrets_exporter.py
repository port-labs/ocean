from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from clients import endpoints
from core.exporters.abstract_exporter import AbstractDevinExporter


class SecretsExporter(AbstractDevinExporter):
    """Secret metadata only: the Devin API never returns secret values."""

    async def get_paginated_resources(  # type: ignore[override]
        self,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for page in self.client.paginate(endpoints.SECRETS):
            yield page

    async def get_resource(self, resource_id: str) -> RAW_ITEM:
        """The API has no single-secret read, so look it up in the list."""
        async for page in self.client.paginate(endpoints.SECRETS):
            for secret in page:
                if secret.get("secret_id") == resource_id:
                    return secret
        return {}
