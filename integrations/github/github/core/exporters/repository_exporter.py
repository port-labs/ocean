import asyncio
from typing import Any, Callable, Dict, List, TYPE_CHECKING, Coroutine
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.client_factory import create_github_client
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import (
    ListGraphQLRepositoryOptions,
    ListRepositoryOptions,
    RepositoryRelationshipOptions,
    SingleGraphQLRepositoryOptions,
    SingleRepositoryOptions,
    GraphQLRepositorySelectorOptions,
)
from github.clients.http.rest_client import GithubRestClient
from github.clients.http.graphql_client import GithubGraphQLClient
from github.helpers.gql_queries import (
    COLLABORATORS_FIELD,
    build_list_repositories_gql,
    build_single_repository_gql,
)

if TYPE_CHECKING:
    from github.clients.http.rest_client import GithubRestClient


class RestRepositoryExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[
        ExporterOptionsT: SingleRepositoryOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        name = options["name"]
        extra_relationship = options.get("extra_relationship")
        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{name}"
        response = await self.client.send_api_request(endpoint)

        logger.info(f"Fetched repository with identifier: {name}")

        if not extra_relationship:
            return response

        return await self.enrich_repository_with_selected_relationship(response, extra_relationship)

    @cache_iterator_result()
    async def get_paginated_resources[
        ExporterOptionsT: ListRepositoryOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""

        params = dict(options)
        extra_relationship = options.get("extra_relationship")

        async for repos in self.client.send_paginated_request(
            f"{self.client.base_url}/orgs/{self.client.organization}/repos", params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.client.organization}"
            )
            if not extra_relationship:
                yield repos
            else:
                batch = [
                    self.enrich_repository_with_selected_relationship(repo, extra_relationship)
                    for repo in repos
                ]
                yield batch

    async def enrich_repository_with_selected_relationship(self, repository: Dict[str, Any], relationship: str) -> RAW_ITEM:
        """Enrich repository with selected relationship."""

        match relationship:
            case "collaborators":
                return await self._enrich_repository_with_collaborators(repository)
            case "teams":
                return await self._enrich_repository_with_teams(repository)
            case _:
                pass

        return repository
        
    async def _enrich_repository_with_collaborators(self, repository: Dict[str, Any]) -> RAW_ITEM:
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

        repository["collaborators"] = all_collaborators
        return repository

    async def _enrich_repository_with_teams(self, repository: Dict[str, Any]) -> RAW_ITEM:
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

        repository["teams"] = all_teams
        return repository
