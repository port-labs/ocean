from typing import Any, AsyncGenerator, TypeAlias, cast
from asyncio import TaskGroup, Semaphore

from loguru import logger
from aws.core.exporters.abstract_exporter import AbstractResourceExporter
from aws.core.options import (
    SingleResourceGroupExporterOptions,
    ListResourceGroupExporterOptions,
    ListGroupResourcesEnricherOptions,
    SupportedServices,
)
from aiobotocore.client import AioBaseClient

ResourceGroupAttributes: TypeAlias = dict[str, Any]


class ResourceGroupExporter(AbstractResourceExporter):
    SERVICE_NAME: SupportedServices = "resource-groups"
    MAX_CONCURRENT_ENRICHMENTS = 20

    async def get_resource(
        self, options: SingleResourceGroupExporterOptions
    ) -> ResourceGroupAttributes:
        """Fetch detailed attributes of a single resource group, optionally enriched with resources."""

        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await getattr(self._client, options.method)(
                Group=options.group,
            )

            if options.include == "resources":
                response["__Resources"] = await self._flattened_group_resources(
                    options.region, options.group
                )

            return response
        except Exception as e:
            logger.error(f"Failed to get resource group {options.group}: {e}")
            raise

    async def get_paginated_resources(
        self, options: ListResourceGroupExporterOptions
    ) -> AsyncGenerator[list[ResourceGroupAttributes], None]:
        """Yield pages of resource groups, enriching each group in parallel if requested."""

        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        semaphore = Semaphore(self.MAX_CONCURRENT_ENRICHMENTS)

        async for groups in self.get_paginated_groups(options):
            if options.include == "resources":

                async def enrich(group: ResourceGroupAttributes) -> None:
                    async with semaphore:
                        try:
                            group["__Resources"] = (
                                await self._flattened_group_resources(
                                    options.region, group["Name"]
                                )
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to enrich group {group['Name']}: {e}"
                            )

                async with TaskGroup() as tg:
                    [
                        tg.create_task(enrich(group))
                        for group in groups
                        if "Name" in group
                    ]

            yield groups

    async def get_paginated_groups(
        self, options: ListResourceGroupExporterOptions
    ) -> AsyncGenerator[list[ResourceGroupAttributes], None]:
        """Yield pages of resource group attributes."""
        client = cast(AioBaseClient, self._client)
        paginator = client.get_paginator(options.method)

        try:
            async for page in paginator.paginate(
                PaginationConfig={"PageSize": options.max_results}
            ):
                yield page.get("Groups", [])
        except Exception as e:
            logger.error(f"Failed to list resource groups: {e}")
            raise

    async def get_paginated_group_resources(
        self, options: ListGroupResourcesEnricherOptions
    ) -> AsyncGenerator[list[ResourceGroupAttributes], None]:
        """Yield pages of resources for a specific group."""

        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        paginator = self._client.get_paginator(options.method)

        try:
            async for page in paginator.paginate(
                Group=options.group,
                PaginationConfig={"PageSize": options.max_results},
            ):
                yield page.get("Resources", [])
        except Exception as e:
            logger.error(f"Failed to list resources for group {options.group}: {e}")
            raise

    async def _flattened_group_resources(
        self, region: str, group_name: str
    ) -> list[dict[str, Any]]:
        """Fetch and flatten all paginated resources for a resource group."""

        resources = []
        async for batch in self.get_paginated_group_resources(
            ListGroupResourcesEnricherOptions(
                region=region,
                group=group_name,
                method="list_group_resources",
            )
        ):
            resources.extend(batch)
        return resources
