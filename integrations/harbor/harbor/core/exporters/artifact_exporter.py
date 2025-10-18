"""Harbor Artifacts Exporter."""

from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.clients.http.harbor_client import HarborClient
from harbor.core.options import ListArtifactOptions, SingleArtifactOptions
from harbor.helpers.utils import build_artifact_params, enrich_artifacts_with_context
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from port_ocean.utils.cache import cache_iterator_result


class HarborArtifactExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor artifacts."""

    async def get_resource(self, options: SingleArtifactOptions) -> RAW_ITEM:
        """Get a single Harbor artifact by project, repository and reference (tag/digest)."""
        project_name = options["project_name"]
        repository_name = options["repository_name"]
        reference = options["reference"]

        logger.info(
            f"Fetching Harbor artifact: {project_name}/{repository_name}:{reference}"
        )

        # Extract just the repository name part (after the last slash) from the full name
        repo_name_only = repository_name.split("/")[-1]

        response = await self.client.make_request(
            f"/projects/{project_name}/repositories/{repo_name_only}/artifacts/{reference}"
        )
        return response.json()

    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: ListArtifactOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all Harbor artifacts with pagination and filtering."""
        logger.info("Starting Harbor artifacts export")

        params = build_artifact_params(options)
        project_name = options["project_name"]
        repository_name = options["repository_name"]

        logger.info(
            f"Fetching artifacts from repository: {project_name}/{repository_name}"
        )

        # Use the correct Harbor API format with project_name and repository_name
        # Extract just the repository name part (after the last slash) from the full name
        # e.g., "opensource/nginx" -> "nginx"
        repo_name_only = repository_name.split("/")[-1]

        endpoint = f"/projects/{project_name}/repositories/{repo_name_only}/artifacts"
        logger.debug(
            f"Using artifacts endpoint: {endpoint} (extracted from {repository_name})"
        )

        async for artifacts_page in self.client.send_paginated_request(
            endpoint,
            params=params,
        ):
            # Enrich artifacts with project_name and repository_name
            enrich_artifacts_with_context(artifacts_page, project_name, repository_name)

            logger.debug(
                f"Fetched {len(artifacts_page)} artifacts from {project_name}/{repository_name}"
            )
            yield artifacts_page
