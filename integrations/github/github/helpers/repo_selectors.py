from abc import ABC, abstractmethod
from functools import lru_cache
import re
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Dict,
    List,
    Optional,
    Tuple,
    TYPE_CHECKING,
    Protocol,
)

from loguru import logger
from port_ocean.utils.cache import cache_iterator_result

from wcmatch import glob

from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from github.core.options import (
    ListOrganizationOptions,
    ListRepositoryOptions,
)
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import get_repository_metadata

if TYPE_CHECKING:
    from github.clients.http.base_client import AbstractGithubClient
    from integration import RepositoryBranchMapping

GLOB_COMPILE_FLAGS = glob.EXTGLOB | glob.BRACE | glob.DOTMATCH | glob.IGNORECASE
GLOB_SPLIT_RE = re.compile(r"[*?\[\]\{\}\(\)\|@]")


class RepoListSelector(Protocol):
    """Minimal selector interface exposing optional repos list."""

    repos: Optional[List["RepositoryBranchMapping"]]


def is_glob(value: str) -> bool:
    return bool(GLOB_SPLIT_RE.search(value))


@lru_cache(maxsize=1024)
def get_compiled_pattern(pattern: str, flags: int = GLOB_COMPILE_FLAGS) -> Any:
    # wcmatch returns a WcMatcher, not a typing.Pattern
    return glob.compile(pattern, flags=flags)


def extract_search_token(pattern: str) -> str | None:
    segments = GLOB_SPLIT_RE.split(pattern)
    valid = [s.strip() for s in segments if any(c.isalnum() for c in s)]
    return max(valid, key=len) if valid else None


def create_search_params(repos: list[str]) -> list[str]:
    """Create search query strings that fits into Github search string limitations.

    Limitations:
        - A search query can be up to 256 characters.
        - A query can contain a maximum of 5 `OR` operators.

    """
    max_operators = 5
    max_repos_in_query = max_operators + 1
    max_search_string_len = 256

    tokens: list[str] = []
    seen: set[str] = set()
    for entry in repos:
        token = extract_search_token(entry)
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)

    search_strings: list[str] = []
    chunk: list[str] = []
    current_query = ""
    for token in tokens:
        repo_query_part = f"{token} in:name"
        if len(repo_query_part) > max_search_string_len:
            logger.warning(
                f"Repository name '{token}' is too long to fit in a search query."
            )
            continue

        if not chunk:
            chunk.append(token)
            current_query = repo_query_part
            continue

        next_query = f"{current_query} OR {repo_query_part}"

        if (
            len(chunk) + 1 > max_repos_in_query
            or len(next_query) > max_search_string_len
        ):
            search_strings.append(current_query)
            chunk = [token]
            current_query = repo_query_part
        else:
            chunk.append(token)
            current_query = next_query

    if chunk:
        search_strings.append(current_query)

    return search_strings


@cache_iterator_result()
async def search_for_repositories(
    client: "AbstractGithubClient", organization: str, repos: list[str]
) -> AsyncIterator[list[dict[str, Any]]]:
    """Search Github for a list of repositories and cache the result"""

    tasks = []
    for search_string in create_search_params(repos):
        logger.debug(f"creating a search task for search string: {search_string}")
        query = f"org:{organization} {search_string} fork:true"
        url = f"{client.base_url}/search/repositories"
        params = {"q": query}
        tasks.append(client.send_paginated_request(url, params=params))

    async for search_result in stream_async_iterators_tasks(*tasks):
        fetched_repos: list[dict[str, Any]] = search_result["items"]
        logger.info(
            f"Found {len(fetched_repos)} repositories for organization {organization}"
        )
        yield fetched_repos


class RepositorySelectorStrategy(ABC):
    """Strategy interface for resolving repositories for a selector.

    Implementations yield tuples of (repo_name, branch, repo_obj) for an
    organization login and a given selector configuration.
    """

    @abstractmethod
    def select_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
    ) -> AsyncIterator[Tuple[str, str, Dict[str, Any]]]:
        """Yield (repo_name, branch, repo_obj)"""
        ...


class AllRepositorySelector(RepositorySelectorStrategy):
    """Select all repositories of the provided repo_type within an organization."""

    def __init__(self, repo_type: str):
        self.repo_type = repo_type

    async def select_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
    ) -> AsyncIterator[Tuple[str, str, Dict[str, Any]]]:
        logger.info(f"Fetching all '{self.repo_type}' repositories from '{org_login}'.")
        options = ListRepositoryOptions(organization=org_login, type=self.repo_type)
        async for batch in repo_exporter.get_paginated_resources(options):
            for repo in batch:
                name = repo["name"]
                default_branch = repo["default_branch"]
                logger.debug(
                    f"Fetched repo '{name}' with default branch '{default_branch}'"
                )
                yield name, default_branch, repo


class ExactRepositorySelector(RepositorySelectorStrategy):
    """Select only explicitly listed repositories (non-glob entries).

    For each explicit repository, repository metadata is fetched to determine a
    branch fallback when the selector omits a branch.
    """

    async def select_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
    ) -> AsyncIterator[Tuple[str, str, Dict[str, Any]]]:
        if not selector.repos:
            return

        for repo_sel in selector.repos:
            if is_glob(repo_sel.name):
                continue
            repo_obj = await get_repository_metadata(
                repo_exporter.client, org_login, repo_sel.name
            )
            branch = repo_sel.branch or repo_obj["default_branch"]
            yield repo_sel.name, branch, repo_obj


class GlobRepositorySelector(RepositorySelectorStrategy):
    """Resolve repositories via glob patterns.

    Performs a repository search per organization, matches names against the
    compiled glob patterns, and yields each matched repository at most once.
    """

    async def select_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
    ) -> AsyncIterator[Tuple[str, str, Dict[str, Any]]]:
        glob_sels = [sel for sel in (selector.repos or []) if is_glob(sel.name)]
        if not glob_sels:
            logger.info(
                f"No glob patterns found in selector for organization '{org_login}'"
            )
            return

        patterns = [sel.name for sel in glob_sels]
        compiled_patterns: list[tuple["re.Pattern[str]", "RepositoryBranchMapping"]] = [
            (get_compiled_pattern(sel.name), sel) for sel in glob_sels
        ]

        logger.info(
            f"Resolving {len(glob_sels)} glob patterns in '{org_login}': {patterns}"
        )
        async for batch in search_for_repositories(
            repo_exporter.client, org_login, patterns
        ):
            for repo in batch:
                repo_name = repo["name"]
                for compiled, repo_sel in compiled_patterns:
                    if compiled.match(repo_name):
                        branch = repo_sel.branch or repo["default_branch"]
                        logger.info(
                            f"Glob match: repository '{repo_name}' matched pattern '{repo_sel.name}' "
                            f"with branch '{branch}' in organization '{org_login}'."
                        )
                        yield repo_name, branch, repo
                        break


class CompositeRepositorySelector(RepositorySelectorStrategy):
    """Composite that orchestrates repository selection strategies.

    When the selector has no explicit repos, it uses the implicit (all) strategy.
    Otherwise, it combines exact and glob strategies.
    """

    def __init__(self, repo_type: str):
        self.implicit_strategies: List[RepositorySelectorStrategy] = [
            AllRepositorySelector(repo_type)
        ]
        self.explicit_strategies: List[RepositorySelectorStrategy] = [
            ExactRepositorySelector(),
            GlobRepositorySelector(),
        ]

    async def select_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
    ) -> AsyncIterator[Tuple[str, str, Dict[str, Any]]]:
        active_strategies = (
            self.explicit_strategies if selector.repos else self.implicit_strategies
        )
        for strategy in active_strategies:
            async for result in strategy.select_repos(
                selector, repo_exporter, org_login
            ):
                yield result


class OrganizationLoginGenerator:
    """Helper to iterate organizations for a selector.

    Wraps the exporter pagination to yield organization logins for a specific
    organization or for all accessible organizations when not provided.
    """

    def __init__(self, org_exporter: AbstractGithubExporter[Any]):
        self.org_exporter = org_exporter

    async def __call__(self, organization: Optional[str]) -> AsyncGenerator[str, None]:
        org_options: ListOrganizationOptions
        if organization:
            org_options = {"organization": organization}
        else:
            org_options = {}
        async for batch in self.org_exporter.get_paginated_resources(org_options):
            for org in batch:
                org_login = org["login"]
                yield org_login
