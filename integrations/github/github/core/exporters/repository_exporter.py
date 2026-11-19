import asyncio
import copy
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, TYPE_CHECKING, Optional, cast, ClassVar
from itertools import batched
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.models import RepoSearchParams
from github.helpers.utils import (
    parse_github_options,
    get_repository_metadata,
    fetch_repository_metadata,
)
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import (
    ListRepositoryOptions,
    SingleRepositoryOptions,
)
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.incremental.strategies import (
    ClientSideCutoffStrategy,
    paginate_with_strategy,
)

REPOSITORY_INCREMENTAL = ClientSideCutoffStrategy(
    stop_field="updated_at",
    query_params={"sort": "updated", "direction": "desc"},
)


REPOSITORY_SEARCH_INCREMENTAL = ClientSideCutoffStrategy(
    stop_field="updated_at",
    query_params={"sort": "updated", "order": "desc"},
)

REPOSITORY_PUSHED_INCREMENTAL = ClientSideCutoffStrategy(
    stop_field="pushed_at",
    query_params={"sort": "pushed", "direction": "desc"},
)

if TYPE_CHECKING:
    from github.clients.http.rest_client import GithubRestClient

ENRICHMENT_BATCH_SIZE = 10
# Repositories checked against the search query in one search request.
REPOSITORIES_PER_SEARCH = 50

ARCHIVED_QUALIFIER_PATTERN = re.compile(
    r"(?<!\S)archived:(?:true|false)(?!\S)", re.IGNORECASE
)


class RestRepositoryExporter(AbstractGithubExporter[GithubRestClient]):
    _ENRICHMENT_METHODS: ClassVar[dict[str, str]] = {
        "collaborators": "_enrich_repository_with_collaborators",
        "teams": "_enrich_repository_with_teams",
        "sbom": "_enrich_repository_with_sbom",
        "custom_properties": "_enrich_repository_with_custom_properties",
        "pages": "_enrich_repository_with_pages",
    }

    async def get_resource[ExporterOptionsT: SingleRepositoryOptions](
        self, options: ExporterOptionsT, *, skip_metadata_cache: bool = False
    ) -> Optional[RAW_ITEM]:
        name = options["name"]
        organization = options["organization"]
        included_relations = options.get("included_relations")

        fetch = (
            fetch_repository_metadata
            if skip_metadata_cache
            else get_repository_metadata
        )
        response = await fetch(self.client, organization, name)
        if not response:
            logger.warning(
                f"No repository found with identifier: {name} for organization {organization}"
            )
            return None

        logger.info(
            f"Fetched repository with identifier: {name} for organization {organization}"
        )

        if not included_relations:
            return response

        return await self.enrich_repository_with_selected_relationships(
            response,
            cast(dict[str, dict[str, Any]], included_relations),
            organization,
        )

    async def get_paginated_resources[ExporterOptionsT: ListRepositoryOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""
        organization = options["organization"]
        options_dict = dict(options)
        included_relations = options_dict.pop("included_relations", None)
        incremental_cursor = options_dict.pop("updated_since", None)
        pushed_since = options_dict.pop("pushed_since", None)

        async for repos in self._fetch_repositories(
            cast(ListRepositoryOptions, options_dict),
            incremental_cursor=incremental_cursor,
            pushed_since=pushed_since,
        ):
            if not included_relations:
                yield repos
                continue

            included_relations = cast(dict[str, dict[str, Any]], included_relations)
            logger.info(
                f"Enriching repositories with {list(included_relations.keys())}"
            )

            for batch in batched(repos, ENRICHMENT_BATCH_SIZE):
                enriched = await asyncio.gather(
                    *[
                        self.enrich_repository_with_selected_relationships(
                            copy.deepcopy(repo),
                            included_relations,
                            organization,
                        )
                        for repo in batch
                    ]
                )
                yield enriched

    @cache_iterator_result()
    async def _fetch_repositories(
        self,
        options: ListRepositoryOptions,
        *,
        incremental_cursor: datetime | None = None,
        pushed_since: datetime | None = None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        _, organization, params = parse_github_options(dict(options))
        organization_type = params.pop("organization_type")
        search_params = cast(
            Optional[RepoSearchParams], params.pop("search_params", None)
        )
        exclude_archived = params.pop("exclude_archived", False)
        is_personal_account = organization_type == "User"
        is_github_app_authenticated = isinstance(
            self.client.authenticator, GitHubAppInstallationAuthenticator
        )

        can_list_repositories = not (
            is_github_app_authenticated and is_personal_account
        )
        strategy: Callable[..., ASYNC_GENERATOR_RESYNC_TYPE]
        if search_params is not None and pushed_since and can_list_repositories:
            strategy = self._pushed_search_strategy
        elif search_params is not None or not can_list_repositories:
            strategy = self._search_strategy
        else:
            strategy = self._list_strategy

        async for batch in strategy(
            organization,
            organization_type,
            params,
            search_params,
            incremental_cursor=incremental_cursor,
            pushed_since=pushed_since,
            exclude_archived=exclude_archived,
        ):
            if exclude_archived:
                batch = [repo for repo in batch if not repo.get("archived")]
                if not batch:
                    continue
            yield batch

    async def _list_strategy(
        self,
        organization: str,
        organization_type: str,
        params: dict[str, Any],
        _: Optional[RepoSearchParams],
        *,
        incremental_cursor: datetime | None = None,
        pushed_since: datetime | None = None,
        exclude_archived: bool = False,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        strategy, cursor = (
            (REPOSITORY_PUSHED_INCREMENTAL, pushed_since)
            if pushed_since
            else (REPOSITORY_INCREMENTAL, incremental_cursor)
        )
        url, final_params = self._build_repos_url_and_params(
            organization,
            organization_type,
            strategy.merge_params(params, cursor),
        )

        async for repos in paginate_with_strategy(
            self.client.send_paginated_request(url, final_params),
            cursor=cursor,
            strategy=strategy,
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {organization}"
            )
            yield repos

    async def _pushed_search_strategy(
        self,
        organization: str,
        organization_type: str,
        params: dict[str, Any],
        search_params: Optional[RepoSearchParams],
        *,
        incremental_cursor: datetime | None = None,
        pushed_since: datetime | None = None,
        exclude_archived: bool = False,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Repositories pushed since ``pushed_since`` that match the search query.

        The search index updates a repository's push time late (a tag push did not
        update it after 10 minutes), so a ``pushed:`` qualifier misses recent pushes.
        The pushed repositories come from the live list instead, and search only
        checks which of them match the query. The list is not limited to the
        repository type: as on a full resync, the query decides that.
        """
        query = search_params.query.strip() if search_params else ""
        async for pushed in self._list_strategy(
            organization,
            organization_type,
            {**params, "type": "all"},
            None,
            pushed_since=pushed_since,
        ):
            matching = await self._repositories_matching_query(
                organization, query, [repo["name"] for repo in pushed]
            )
            repos = [repo for repo in pushed if repo["name"] in matching]
            if repos:
                yield repos

    async def _repositories_matching_query(
        self, organization: str, query: str, names: list[str]
    ) -> set[str]:
        """The repositories among ``names`` that match the search ``query``.

        They are named with ``repo:`` qualifiers and no ``org:``: search combines
        ``org:`` and ``repo:`` with OR, which would match the whole organization.
        """
        url = f"{self.client.base_url}/search/repositories"
        matching: set[str] = set()
        for names_batch in batched(names, REPOSITORIES_PER_SEARCH):
            repo_qualifiers = " ".join(
                f"repo:{organization}/{name}" for name in names_batch
            )
            async for items in self._search_result_items(
                url, {"q": f"{query} {repo_qualifiers}".strip()}
            ):
                matching.update(item["name"] for item in items)
        return matching

    async def _search_strategy(
        self,
        organization: str,
        _: str,
        params: dict[str, Any],
        search_params: Optional[RepoSearchParams],
        *,
        incremental_cursor: datetime | None = None,
        pushed_since: datetime | None = None,
        exclude_archived: bool = False,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        repository_type = params.pop("type")
        forced_qualifiers = (
            ["fork:true", f"is:{repository_type}"] if search_params is None else []
        )

        raw_q = (
            search_params.query.strip()
            if search_params
            else " ".join(forced_qualifiers).strip()
        )

        if exclude_archived:
            if ARCHIVED_QUALIFIER_PATTERN.search(raw_q):
                raw_q = ARCHIVED_QUALIFIER_PATTERN.sub("archived:false", raw_q).strip()
            else:
                raw_q = f"{raw_q} archived:false".strip() if raw_q else "archived:false"

        if pushed_since:
            # Search has no "pushed" sort, so filter server-side with a qualifier instead.
            raw_q = (
                f"{raw_q} pushed:>={self._format_search_datetime(pushed_since)}".strip()
            )
            incremental_cursor = None

        query_params = {
            "q": f"org:{organization} {raw_q}",
            **REPOSITORY_SEARCH_INCREMENTAL.merge_params(params, incremental_cursor),
        }
        url = f"{self.client.base_url}/search/repositories"

        async for repos in paginate_with_strategy(
            self._search_result_items(url, query_params),
            cursor=incremental_cursor,
            strategy=REPOSITORY_SEARCH_INCREMENTAL,
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from search for organization {organization}"
            )
            yield repos

    @staticmethod
    def _format_search_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    async def _search_result_items(
        self, url: str, query_params: dict[str, Any]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Unwrap the search API envelope so pages are plain repository lists."""
        async for search_results in self.client.send_paginated_request(
            url, query_params
        ):
            casted = cast(dict[str, Any], search_results)
            yield casted["items"]

    def _build_repos_url_and_params(
        self, organization: str, organization_type: str, params: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """
        Build the appropriate repositories API URL and parameters
        based on the organization type.
        """
        if organization_type == "Organization":
            return (
                f"{self.client.base_url}/orgs/{organization}/repos",
                params,
            )
        visibility = params.pop("type")
        return f"{self.client.base_url}/user/repos", {
            **params,
            "affiliation": "owner",
            "visibility": visibility,
        }

    async def enrich_repository_with_selected_relationships(
        self,
        repository: Dict[str, Any],
        included_relations: dict[str, dict[str, Any]],
        organization: str,
    ) -> RAW_ITEM:
        """Enrich a repository with selected relationships."""
        repo_name = repository["name"]

        for relationship, config in included_relations.items():
            method_name = self._ENRICHMENT_METHODS.get(relationship)
            if method_name and config.get("include"):
                logger.debug(
                    f"Applying relationship '{relationship}' using '{method_name}' "
                    f"for repository '{repo_name}'"
                )
                method = getattr(self, method_name)
                repository = await method(repository, organization, config)

        logger.info(f"Finished enrichment for repository '{repo_name}'")
        return repository

    async def _enrich_repository_with_collaborators(
        self, repository: Dict[str, Any], organization: str, config: dict[str, Any]
    ) -> RAW_ITEM:
        """Enrich repository with collaborators."""
        repo_name = repository["name"]
        affiliation = config.get("affiliation", "all")
        params = {"affiliation": affiliation}

        all_collaborators = []

        async for collaborators in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/collaborators",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(collaborators)} collaborators for repository {repo_name} in repository relationship with params: {params}"
            )
            all_collaborators.extend(collaborators)

        repository["__collaborators"] = all_collaborators
        return repository

    async def _enrich_repository_with_teams(
        self, repository: Dict[str, Any], organization: str, config: dict[str, Any]
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

    async def _enrich_repository_with_custom_properties(
        self, repository: Dict[str, Any], organization: str, config: dict[str, Any]
    ) -> RAW_ITEM:
        if "custom_properties" in repository:
            return repository
        repo_name = repository["name"]
        logger.info(
            f"Fetching custom properties for repository {repo_name} in organization {organization}"
        )
        properties = cast(
            list[Dict[str, Any]],
            await self.client.send_api_request(
                f"{self.client.base_url}/repos/{organization}/{repo_name}/properties/values"
            ),
        )
        repository["custom_properties"] = (
            {prop["property_name"]: prop["value"] for prop in properties}
            if properties
            else {}
        )
        logger.info(
            f"Fetched {len(repository['custom_properties'])} custom properties for repository {repo_name} in organization {organization}"
        )
        return repository

    async def _enrich_repository_with_sbom(
        self, repository: Dict[str, Any], organization: str, config: dict[str, Any]
    ) -> RAW_ITEM:
        repo_name = repository["name"]

        url = f"{self.client.base_url}/repos/{organization}/{repo_name}/dependency-graph/sbom"
        response = await self.client.send_api_request(url)
        if not response:
            logger.warning(
                f"No SBOM found for repository {repo_name} in organization {organization}"
            )
            repository["__sbom"] = {}
            return repository

        repository["__sbom"] = response.get("sbom", {})
        return repository

    async def _enrich_repository_with_pages(
        self, repository: Dict[str, Any], organization: str, config: dict[str, Any]
    ) -> RAW_ITEM:
        repo_name = repository["name"]

        url = f"{self.client.base_url}/repos/{organization}/{repo_name}/pages"
        response = await self.client.send_api_request(url)
        if not response:
            logger.debug(
                f"Skipping GitHub Pages enrichment for repository {repo_name} in organization {organization}: empty response"
            )
            repository["__pages"] = {}
            return repository

        repository["__pages"] = response
        return repository
