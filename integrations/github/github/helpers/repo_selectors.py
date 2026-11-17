from abc import ABC, abstractmethod
from datetime import datetime
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Optional,
    Tuple,
    TYPE_CHECKING,
    Protocol,
)

from loguru import logger
from port_ocean.utils.time import convert_str_to_utc_datetime


from github.core.options import ListRepositoryOptions
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import get_repository_metadata

if TYPE_CHECKING:
    from integration import RepositoryBranchMapping


class RepoListSelector(Protocol):
    """Minimal selector interface exposing optional repos list."""

    repos: Optional[List["RepositoryBranchMapping"]]
    exclude_archived: bool


def _pushed_since(repo_obj: Dict[str, Any], pushed_since: Optional[datetime]) -> bool:
    """True when there is no filter, or the repo was pushed since then (a missing `pushed_at` counts as pushed)."""
    pushed_at = repo_obj.get("pushed_at")
    if pushed_since is None or not pushed_at:
        return True
    return convert_str_to_utc_datetime(pushed_at) >= pushed_since


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
        org_type: str,
        pushed_since: Optional[datetime] = None,
    ) -> AsyncIterator[Tuple[str, str, Dict[str, Any]]]:
        """Yield (repo_name, branch, repo_obj), optionally only repos pushed since *pushed_since*."""
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
        org_type: str,
        pushed_since: Optional[datetime] = None,
    ) -> AsyncIterator[Tuple[str, str, Dict[str, Any]]]:
        logger.info(
            f"Fetching all '{self.repo_type}' repositories from '{org_login}' of type '{org_type}'."
        )
        options = ListRepositoryOptions(
            organization=org_login,
            organization_type=org_type,
            type=self.repo_type,
            exclude_archived=selector.exclude_archived,
            pushed_since=pushed_since,
        )
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

    Note: explicitly listed repos are always included regardless of
    `exclude_archived` on the selector - the same precedent already applies to
    `repo_search`/`search_params`, which are likewise never consulted here.
    """

    async def select_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
        org_type: str,
        pushed_since: Optional[datetime] = None,
    ) -> AsyncIterator[Tuple[str, str, Dict[str, Any]]]:
        if not selector.repos:
            return

        for repo_sel in selector.repos:
            repo_obj = await get_repository_metadata(
                repo_exporter.client, org_login, repo_sel.name
            )
            if not repo_obj:
                logger.warning(f"Repository {repo_sel.name} not found in {org_login}")
                continue
            if not _pushed_since(repo_obj, pushed_since):
                continue

            branch = repo_sel.branch or repo_obj["default_branch"]
            yield repo_sel.name, branch, repo_obj


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
            ExactRepositorySelector()
        ]

    async def select_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
        org_type: str,
        pushed_since: Optional[datetime] = None,
    ) -> AsyncIterator[Tuple[str, str, Dict[str, Any]]]:
        active_strategies = (
            self.explicit_strategies if selector.repos else self.implicit_strategies
        )
        for strategy in active_strategies:
            async for result in strategy.select_repos(
                selector, repo_exporter, org_login, org_type, pushed_since
            ):
                yield result
