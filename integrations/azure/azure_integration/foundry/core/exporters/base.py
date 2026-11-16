from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.options import ProjectIdentifier

TOptions = TypeVar("TOptions", bound=ProjectIdentifier)


class FoundryExporter(Generic[TOptions]):
    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    async def get_paginated_resources(
        self, options: TOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise NotImplementedError
        yield  # pragma: no cover — async-generator typing for subclasses

    async def get_paginated_resources_across_projects(
        self,
        *,
        resource_label: str,
        project_api_version: str,
        regions: list[str],
        build_options: Callable[[str, str], TOptions],
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        # Late import: ProjectExporter pulls ARM clients; keep data-plane exporters light.
        from azure_integration.foundry.core.exporters.project_exporter import (
            ProjectExporter,
        )

        async for projects in ProjectExporter().get_paginated_resources(
            api_version=project_api_version,
            regions=regions,
        ):
            for project in projects:
                project_endpoint = str(project["__foundryProjectEndpoint"])
                logger.info(
                    f"Syncing Foundry {resource_label} for project "
                    f"{project['name']} ({project_endpoint})"
                )
                async for page in self.get_paginated_resources(
                    build_options(project_endpoint, str(project["id"]))
                ):
                    yield page
