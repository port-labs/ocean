"""Harbor Artifacts Exporter."""

from typing import Any, cast

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.core.options import ListArtifactOptions


class HarborArtifactExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor artifacts."""

    ENRICH_CONCURRENCY: int = 10

    def _enrich_artifacts_with_context(
        self,
        artifacts: list[dict[str, Any]],
        project_name: str,
        repository_name: str,
    ) -> None:
        """Enrich artifacts with project and repository context.

        Args:
            artifacts: List of artifacts to enrich
            project_name: The project name
            repository_name: The repository name
        """
        for artifact in artifacts:
            artifact["__project"] = project_name
            artifact["__repository"] = repository_name

    async def get_resource(
        self,
        project_name: str,
        repository_name: str,
        reference: str,
    ) -> RAW_ITEM:
        """Get a single Harbor artifact.

        Args:
            project_name: Name of the project
            repository_name: Name of the repository
            reference: Artifact reference (tag or digest)

        Returns:
            Artifact data
        """
        logger.info(f"Fetching Harbor artifact: {project_name}/{repository_name}:{reference}")

        repo_name_only = repository_name.split("/")[-1]

        return cast(
            RAW_ITEM,
            await self.client.send_api_request(
                f"/projects/{project_name}/repositories/{repo_name_only}/artifacts/{reference}"
            ),
        )

    @cache_iterator_result()
    async def get_paginated_resources(self, options: ListArtifactOptions) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all Harbor artifacts with pagination and enrichment.

        Args:
            options: Options including project, repository, and enrichment flags

        Yields:
            Batches of enriched artifacts
        """
        project_name = options["project_name"]
        repository_name = options["repository_name"]

        logger.info(f"Starting Harbor artifacts export for {project_name}/{repository_name}")

        params = {}

        if q := options.get("q"):
            params["q"] = q

        if sort := options.get("sort"):
            params["sort"] = sort

        if with_tag := options.get("with_tag"):
            params["with_tag"] = with_tag

        if with_label := options.get("with_label"):
            params["with_label"] = with_label

        if with_scan_overview := options.get("with_scan_overview"):
            params["with_scan_overview"] = with_scan_overview

        if with_signature := options.get("with_signature"):
            params["with_signature"] = with_signature

        if with_immutable_status := options.get("with_immutable_status"):
            params["with_immutable_status"] = with_immutable_status

        if with_accessory := options.get("with_accessory"):
            params["with_accessory"] = with_accessory

        repo_name_only = repository_name.split("/")[-1]
        endpoint = f"/projects/{project_name}/repositories/{repo_name_only}/artifacts"

        async for artifacts_page in self.client.send_paginated_request(endpoint, params=params):
            self._enrich_artifacts_with_context(artifacts_page, project_name, repository_name)

            logger.debug(f"Fetched {len(artifacts_page)} artifacts from {project_name}/{repository_name}")
            yield artifacts_page
