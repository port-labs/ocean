"""Artifact exporter for Harbor integration."""

import asyncio
from functools import partial
from typing import Any, Dict, List, Optional, Tuple, cast

import httpx
from loguru import logger

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.core.options import GetArtifactOptions, ListArtifactOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)


class HarborArtifactExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor artifacts."""

    ENRICH_CONCURRENCY: int = 10

    async def get_resource(self, options: GetArtifactOptions) -> Optional[RAW_ITEM]:
        """Get a single artifact resource.

        Args:
            options: Options containing project_name, repository_name, and reference

        Returns:
            Artifact data or None if not found
        """
        project_name = options["project_name"]
        repository_name = options["repository_name"]
        reference = options["reference"]

        endpoint = (
            f"projects/{project_name}/repositories/{repository_name}"
            f"/artifacts/{reference}"
        )

        logger.debug(f"Fetching artifact: {project_name}/{repository_name}:{reference}")

        try:
            artifact = await self.client.send_api_request(endpoint)
            logger.debug(f"Successfully fetched artifact: {artifact.get('digest')}")
            return cast(RAW_ITEM, artifact)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Artifact not found: {project_name}/{repository_name}/{reference}"
                )
                return None
            raise

        except Exception as e:
            logger.error(
                f"Failed to fetch artifact "
                f"{project_name}/{repository_name}/{reference}: {str(e)}"
            )
            raise

    async def get_paginated_resources(
        self, options: Optional[ListArtifactOptions] = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get artifacts with pagination support.

        This method fetches all repositories first, then fetches artifacts
        for each repository concurrently using a semaphore for rate limiting.

        Args:
            options: Options for filtering artifacts

        Yields:
            List of artifacts from each batch
        """
        params = self._build_artifact_params(options)

        logger.info(f"Starting resync for Harbor artifacts with params: {params}")

        semaphore = asyncio.Semaphore(self.ENRICH_CONCURRENCY)

        async for response in self.client.send_paginated_request("repositories", {}):
            repositories_batch = self._extract_items_from_response(response)
            if not repositories_batch:
                continue

            logger.info(
                f"Processing batch of {len(repositories_batch)} repositories for artifacts"
            )

            tasks = []
            for repository in repositories_batch:
                repo_name = repository.get("name", "")

                try:
                    project_name, repository_name = self._split_repository_name(
                        repo_name
                    )
                except ValueError as e:
                    logger.warning(f"Skipping repository due to invalid name: {str(e)}")
                    continue

                tasks.append(
                    semaphore_async_iterator(
                        semaphore,
                        partial(
                            self._create_artifact_iterator,
                            project_name,
                            repository_name,
                            repo_name,
                            params,
                        ),
                    )
                )

            if tasks:
                async for artifacts_batch in stream_async_iterators_tasks(*tasks):
                    yield artifacts_batch

    @staticmethod
    def _build_artifact_params(
        options: Optional[ListArtifactOptions],
    ) -> Dict[str, Any]:
        """Build query parameters from artifact options.

        Args:
            options: Artifact filter options

        Returns:
            Dictionary of query parameters
        """
        params: Dict[str, Any] = {}

        if not options:
            return params

        tag = options.get("tag")
        digest = options.get("digest")
        label = options.get("label")
        media_type = options.get("media_type")
        created_since = options.get("created_since")

        if tag:
            params["q"] = f"tags={tag}"
        if digest:
            params["digest"] = digest
        if label:
            params["with_label"] = label
        if media_type:
            params["media_type"] = media_type
        if created_since:
            params["q"] = f"creation_time>={created_since}"

        return params

    @staticmethod
    def _split_repository_name(repository_name: str) -> Tuple[str, str]:
        """Split a full repository name into project and repository components.

        Harbor repositories are stored in the format: "project_name/repository_name"

        Args:
            repository_name: Full repository name (e.g., "library/nginx")

        Returns:
            Tuple of (project_name, repository_name)

        Raises:
            ValueError: If the repository name format is invalid
        """
        if not repository_name or "/" not in repository_name:
            raise ValueError(f"Invalid repository name format: {repository_name}")

        parts = repository_name.split("/", 1)
        return parts[0], parts[1]

    async def _create_artifact_iterator(
        self,
        project_name: str,
        repository_name: str,
        repo_full_name: str,
        params: Dict[str, Any],
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Fetch artifacts for a single repository.

        This is an async generator that yields batches of artifacts from a Harbor repository.

        Args:
            project_name: Project name
            repository_name: Repository name
            repo_full_name: Full repository name (project/repo) for logging purposes
            params: Query parameters for filtering artifacts

        Yields:
            Batches of artifact dictionaries
        """
        endpoint = f"projects/{project_name}/repositories/{repository_name}/artifacts"

        try:
            logger.debug(f"Fetching artifacts for repository: {repo_full_name}")
            async for response in self.client.send_paginated_request(endpoint, params):
                artifacts_batch = self._extract_items_from_response(response)
                if artifacts_batch:
                    logger.debug(
                        f"Received {len(artifacts_batch)} artifacts from {repo_full_name}"
                    )
                    yield artifacts_batch
        except Exception as e:
            logger.error(
                f"Failed to fetch artifacts for repository {repo_full_name}: {str(e)}"
            )
            return

