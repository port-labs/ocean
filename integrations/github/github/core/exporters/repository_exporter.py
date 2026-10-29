import asyncio
import copy
import re
from datetime import datetime, timezone
from typing import Any, Dict, TYPE_CHECKING, Optional, cast, ClassVar
from itertools import batched
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.models import RepoSearchParams
from github.helpers.repository_change import RepositoryChange, RepositoryChangeField
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

# How each change field is applied: list endpoints sort by it and stop at the cursor.
LIST_CHANGE_STRATEGIES: dict[RepositoryChangeField, ClientSideCutoffStrategy] = {
    RepositoryChangeField.UPDATED: REPOSITORY_INCREMENTAL,
    RepositoryChangeField.PUSHED: REPOSITORY_PUSHED_INCREMENTAL,
}
# Search can sort by "updated" but not "pushed", so pushed is filtered server-side by qualifier.
SEARCH_CHANGE_STRATEGIES: dict[RepositoryChangeField, ClientSideCutoffStrategy] = {
    RepositoryChangeField.UPDATED: REPOSITORY_SEARCH_INCREMENTAL,
}
SEARCH_CHANGE_QUALIFIERS: dict[RepositoryChangeField, str] = {
    RepositoryChangeField.PUSHED: "pushed",
}

if TYPE_CHECKING:
    from github.clients.http.rest_client import GithubRestClient

ENRICHMENT_BATCH_SIZE = 10

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
        changed_since = cast(
            Optional[RepositoryChange], options_dict.pop("changed_since", None)
        )

        async for repos in self._fetch_repositories(
            cast(ListRepositoryOptions, options_dict),
            changed_since=changed_since,
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
        changed_since: Optional[RepositoryChange] = None,
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

        use_search_api = search_params is not None or (
            is_github_app_authenticated and is_personal_account
        )
        strategy = self._search_strategy if use_search_api else self._list_strategy

        async for batch in strategy(
            organization,
            organization_type,
            params,
            search_params,
            changed_since=changed_since,
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
        changed_since: Optional[RepositoryChange] = None,
        exclude_archived: bool = False,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        strategy = (
            LIST_CHANGE_STRATEGIES[changed_since.field] if changed_since else None
        )
        cursor = changed_since.since if changed_since else None
        url, final_params = self._build_repos_url_and_params(
            organization,
            organization_type,
            strategy.merge_params(params, cursor) if strategy else params,
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

    async def _search_strategy(
        self,
        organization: str,
        _: str,
        params: dict[str, Any],
        search_params: Optional[RepoSearchParams],
        *,
        changed_since: Optional[RepositoryChange] = None,
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

        raw_q, strategy, cursor = self._apply_incremental_search_filter(
            raw_q, changed_since
        )

        query_params = {
            "q": f"org:{organization} {raw_q}",
            **(strategy.merge_params(params, cursor) if strategy else params),
        }
        url = f"{self.client.base_url}/search/repositories"

        async for repos in paginate_with_strategy(
            self._search_result_items(url, query_params),
            cursor=cursor,
            strategy=strategy,
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from search for organization {organization}"
            )
            yield repos

    def _apply_incremental_search_filter(
        self, raw_q: str, changed_since: Optional[RepositoryChange]
    ) -> tuple[str, Optional[ClientSideCutoffStrategy], Optional[datetime]]:
        """Narrow a repository search to changes since the cursor.

        Fields GitHub search can filter server-side (pushed) become a date
        qualifier. Fields it can only sort (updated) use a client-side cutoff.
        """
        if not changed_since:
            return raw_q, None, None

        qualifier = SEARCH_CHANGE_QUALIFIERS.get(changed_since.field)
        if qualifier:
            since = self._format_search_datetime(changed_since.since)
            return f"{raw_q} {qualifier}:>={since}".strip(), None, None

        return (
            raw_q,
            SEARCH_CHANGE_STRATEGIES[changed_since.field],
            changed_since.since,
        )

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
