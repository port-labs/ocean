import asyncio
from typing import Any, Dict, TYPE_CHECKING, Optional, cast, ClassVar
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.models import RepoSearchParams
from github.helpers.utils import parse_github_options
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
    _ENRICHMENT_METHODS: ClassVar[dict[str, str]] = {
        "collaborators": "_enrich_repository_with_collaborators",
        "teams": "_enrich_repository_with_teams",
    }

    async def get_resource[
        ExporterOptionsT: SingleRepositoryOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        name = options["name"]
        organization = options["organization"]
        included_relationships = options.get("included_relationships")

        endpoint = f"{self.client.base_url}/repos/{organization}/{name}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched repository with identifier: {name} for organization {organization}"
        )

        if not included_relationships:
            return response

        return await self.enrich_repository_with_selected_relationships(
            response, cast(list[str], included_relationships), organization
        )

    @cache_iterator_result()
    async def get_paginated_resources[
        ExporterOptionsT: ListRepositoryOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""
        organization = options["organization"]
        included_relationships = options.get("included_relationships")

        async for repos in self._fetch_repositories(options):
            if not included_relationships:
                yield repos
            else:
                logger.info(f"Enriching repositories with {included_relationships}")
                batch = await asyncio.gather(
                    *[
                        self.enrich_repository_with_selected_relationships(
                            repo, cast(list[str], included_relationships), organization
                        )
                        for repo in repos
                    ]
                )
                yield batch

    async def _fetch_repositories(
        self, options: ListRepositoryOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        _, organization, params = parse_github_options(dict(options))
        search_params = cast(
            Optional[RepoSearchParams], params.pop("search_params", None)
        )

        if search_params:
            search_query = (
                f"org:{organization} {search_params.query if search_params else ' '}"
            )
            query = {"q": search_query, **params}
            url = f"{self.client.base_url}/search/repositories"
            async for search_results in self.client.send_paginated_request(url, query):
                casted = cast(dict[str, Any], search_results)
                yield casted["items"]
        else:
            url = f"{self.client.base_url}/orgs/{organization}/repos"
            async for repos in self.client.send_paginated_request(url, params):
                logger.info(
                    f"Fetched batch of {len(repos)} repositories from organization {organization}"
                )
                yield repos

    async def enrich_repository_with_selected_relationships(
        self,
        repository: Dict[str, Any],
        included_relationships: list[str],
        organization: str,
    ) -> RAW_ITEM:
        """Enrich a repository with selected relationships."""
        repo_name = repository["name"]

        for relationship in included_relationships:
            method_name = self._ENRICHMENT_METHODS.get(relationship)
            if method_name:
                logger.debug(
                    f"Applying relationship '{relationship}' using '{method_name}' "
                    f"for repository '{repo_name}'"
                )
                method = getattr(self, method_name)
                repository = await method(repository, organization)

        logger.info(f"Finished enrichment for repository '{repo_name}'")
        return repository

    async def _enrich_repository_with_collaborators(
        self, repository: Dict[str, Any], organization: str
    ) -> RAW_ITEM:
        """Enrich repository with collaborators."""
        repo_name = repository["name"]
        all_collaborators = []

        async for collaborators in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/collaborators",
            {},
        ):
            logger.info(
                f"Fetched batch of {len(collaborators)} collaborators for repository {repo_name} in repository relationship"
            )
            all_collaborators.extend(collaborators)

        repository["__collaborators"] = all_collaborators
        return repository

    async def _enrich_repository_with_teams(
        self, repository: Dict[str, Any], organization: str
    ) -> RAW_ITEM:
        """Enrich repository with teams."""
        repo_name = repository["name"]
        all_teams = []

        async for teams in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/teams",
            {},
        ):
            logger.info(
                f"Fetched batch of {len(teams)} teams for repository {repo_name} in repository relationship"
            )
            all_teams.extend(teams)

        repository["__teams"] = all_teams
        return repository
