import asyncio
from typing import Any, Dict, TYPE_CHECKING
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import (
    ListRepositoryOptions,
    SingleRepositoryOptions,
)
from github.clients.http.rest_client import GithubRestClient

if TYPE_CHECKING:
    from github.clients.http.rest_client import GithubRestClient


class RestRepositoryExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[
        ExporterOptionsT: SingleRepositoryOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        name = options["name"]
        included_relationships = options.get("included_relationships")

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{name}"
        response = await self.client.send_api_request(endpoint)

        logger.info(f"Fetched repository with identifier: {name}")

        if not included_relationships:
            return response

        return await self.enrich_repository_with_selected_relationship(
            response, included_relationships
        )

    @cache_iterator_result()
    async def get_paginated_resources[
        ExporterOptionsT: ListRepositoryOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""

        params = dict(options)
        included_relationships = options.get("included_relationships")

        async for repos in self.client.send_paginated_request(
            f"{self.client.base_url}/orgs/{self.client.organization}/repos", params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.client.organization}"
            )
            if not included_relationships:
                yield repos
            else:
                logger.info(f"Enriching repository with {included_relationships}")
                
                relationships_list = list(included_relationships)
                batch = await asyncio.gather(
                    *[
                        self.enrich_repository_with_selected_relationship(
                            repo, relationships_list
                        )
                        for repo in repos
                    ]
                )
                yield batch

    async def enrich_repository_with_selected_relationship(
        self, repository: Dict[str, Any], included_relationships: list[str]
    ) -> RAW_ITEM:
        """Enrich repository with selected relationship."""

        enrichment_methods = {
            "collaborators": self._enrich_repository_with_collaborators,
            "teams": self._enrich_repository_with_teams,
        }

        for relationship in included_relationships:
            if method := enrichment_methods.get(relationship):
                repository = await method(repository)

        return repository

    async def _enrich_repository_with_collaborators(
        self, repository: Dict[str, Any]
    ) -> RAW_ITEM:
        """Enrich repository with collaborators."""
        repo_name = repository["name"]
        all_collaborators = []

        async for collaborators in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/collaborators",
            {},
        ):
            logger.info(
                f"Fetched batch of {len(collaborators)} collaborators for repository {repo_name} in repository relationship"
            )
            all_collaborators.extend(collaborators)

        repository["__collaborators"] = all_collaborators
        return repository

    async def _enrich_repository_with_teams(
        self, repository: Dict[str, Any]
    ) -> RAW_ITEM:
        """Enrich repository with teams."""
        repo_name = repository["name"]
        all_teams = []

        async for teams in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/teams",
            {},
        ):
            logger.info(
                f"Fetched batch of {len(teams)} teams for repository {repo_name} in repository relationship"
            )
            all_teams.extend(teams)

        repository["__teams"] = all_teams
        return repository
