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

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{name}"
        response = await self.client.send_api_request(endpoint)

        logger.info(f"Fetched repository with identifier: {name}")
        return response

    @cache_iterator_result()
    async def get_paginated_resources[
        ExporterOptionsT: ListRepositoryOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""

        params = dict(options)

        async for repos in self.client.send_paginated_request(
            f"{self.client.base_url}/orgs/{self.client.organization}/repos", params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.client.organization}"
            )
            yield repos


class GraphQLRepositoryExporter(AbstractGithubExporter[GithubGraphQLClient]):
    """
    Exports a repository with its collaborators using GraphQL.
    """

    MAX_CONCURRENT_ENRICHES = 10

    async def get_resource[
        ExporterOptionsT: SingleGraphQLRepositoryOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        name = options["name"]
        selector = options["selector"]

        variables = {
            "organization": self.client.organization,
            "repositoryName": name,
            "first": 1,
        }

        additional_fields = self._build_optional_graphql_fields_from_selector(selector)
        payload = self.client.build_graphql_payload(
            build_single_repository_gql(additional_fields=additional_fields), variables
        )

        response = await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )
        if not response:
            logger.error(
                f"Failed to fetch repository with additional fields for identifier: {name}"
            )
            return {}

        logger.info(f"Fetched repository with additional fields for identifier: {name}")

        repo = self._normalize_repository(
            response["data"]["organization"]["repository"]
        )

        enrichers: List[
            Callable[
                [Dict[str, Any], "GithubRestClient"],
                Coroutine[Any, Any, Dict[str, Any]],
            ]
        ] = []
        rest_client = create_github_client()

        if selector["teams"]:
            enrichers.append(self._enrich_repository_with_teams)

        if selector["custom_properties"]:
            enrichers.append(self._enrich_repository_with_custom_properties)

        if enrichers:
            semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_ENRICHES)
            repo = await self._run_enrichers_for_repository(
                repo, enrichers, semaphore, rest_client
            )

        logger.info(f"Fetched and enriched repository for identifier: {name}")
        return repo

    @cache_iterator_result()
    async def get_paginated_resources[
        ExporterOptionsT: ListGraphQLRepositoryOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:

        repository_type = options["type"]
        selector = options["selector"]

        variables = {
            "organization": self.client.organization,
            "__path": "organization.repositories",
        }

        if repository_type != "all":
            variables["repositoryVisibility"] = repository_type.upper()

        additional_fields = self._build_optional_graphql_fields_from_selector(selector)
        payload = build_list_repositories_gql(additional_fields=additional_fields)

        enrichers: List[
            Callable[
                [Dict[str, Any], "GithubRestClient"],
                Coroutine[Any, Any, Dict[str, Any]],
            ]
        ] = []
        rest_client = create_github_client()

        if selector["teams"]:
            enrichers.append(self._enrich_repository_with_teams)

        if selector["custom_properties"]:
            enrichers.append(self._enrich_repository_with_custom_properties)

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_ENRICHES)

        async for repositories in self.client.send_paginated_request(
            payload, params=variables
        ):
            repositories = [self._normalize_repository(repo) for repo in repositories]

            if enrichers:
                enriched_repos_tasks = [
                    self._run_enrichers_for_repository(
                        repo, enrichers, semaphore, rest_client
                    )
                    for repo in repositories
                ]
                enriched_repos = await asyncio.gather(*enriched_repos_tasks)
            else:
                enriched_repos = repositories

            logger.info(
                f"Fetched batch of {len(enriched_repos)} repositories from organization {self.client.organization}"
            )
            yield enriched_repos

    def _build_optional_graphql_fields_from_selector(
        self, selector: GraphQLRepositorySelectorOptions
    ) -> str:
        """Get additional fields based on selector configuration."""
        additional_fields = [
            field
            for field_name, field in [
                ("collaborators", COLLABORATORS_FIELD),
            ]
            if selector.get(field_name)
        ]
        return (
            self._combine_repository_fields(*additional_fields)
            if additional_fields
            else ""
        )

    def _combine_repository_fields(self, *fields: str) -> str:
        """Combine multiple repository fields into a single string."""
        return "\n".join(fields)

    def _normalize_repository(self, repository: Dict[str, Any]) -> Dict[str, Any]:
        if "visibility" in repository:
            repository["visibility"] = repository["visibility"].lower()

        if "collaborators" in repository and isinstance(
            repository["collaborators"], dict
        ):
            repository["collaborators"] = repository["collaborators"].get("nodes", [])

        return repository

    async def _enrich_repository_with_teams(
        self, repository: Dict[str, Any], client: "GithubRestClient"
    ) -> Dict[str, Any]:
        """Get teams from repositories."""

        logger.info(f"Fetching teams for repository: {repository['name']}")

        teams = await client.send_api_request(
            f"{client.base_url}/repos/{client.organization}/{repository['name']}/teams"
        )

        return {"teams": teams}

    async def _enrich_repository_with_custom_properties(
        self, repository: Dict[str, Any], client: "GithubRestClient"
    ) -> Dict[str, Any]:
        """Enrich repository with custom properties."""
        logger.info(
            f"Enriching repository with custom properties: {repository['name']}"
        )

        custom_properties = await client.send_api_request(
            f"{client.base_url}/repos/{client.organization}/{repository['name']}/properties/values"
        )

        return {"customProperties": custom_properties}

    async def _run_enrichers_for_repository(
        self,
        repo: Dict[str, Any],
        enrichers: List[
            Callable[
                [Dict[str, Any], "GithubRestClient"],
                Coroutine[Any, Any, Dict[str, Any]],
            ]
        ],
        semaphore: asyncio.Semaphore,
        client: "GithubRestClient",
    ) -> Dict[str, Any]:
        async with semaphore:
            # Run enrichers concurrently
            enriched_parts = await asyncio.gather(
                *(enricher(repo.copy(), client) for enricher in enrichers)
            )
            for partial in enriched_parts:
                repo.update(partial)
            return repo
