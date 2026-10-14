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


from github.core.options import ListRepositoryOptions
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import get_repository_metadata, parse_timestamp

if TYPE_CHECKING:
    from integration import RepositoryBranchMapping


def is_pushed_since(repo: Dict[str, Any], pushed_since: datetime) -> bool:
    """Return True when the repo was pushed at or after ``pushed_since`` (unknown counts as pushed)."""
    raw_pushed_at = repo.get("pushed_at")
    pushed_at = parse_timestamp(raw_pushed_at) if raw_pushed_at else None
    return pushed_at is None or pushed_at >= pushed_since


class RepoListSelector(Protocol):
    """Minimal selector interface exposing optional repos list."""

    repos: Optional[List["RepositoryBranchMapping"]]
    exclude_archived: bool


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
        )
        if pushed_since:
            options["pushed_since"] = pushed_since
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

            if pushed_since and not is_pushed_since(repo_obj, pushed_since):
                logger.debug(
                    f"Skipping repository {repo_sel.name}: not pushed since {pushed_since.isoformat()}"
                )
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


class MemoizedRepositorySelector:
    """Lists an org's repositories once per build for selectors without explicit repos.

    Selectors that only differ in path/content options resolve to the same repo
    list request, so later selectors reuse the first result (including an empty
    one, which the Ocean cache does not reuse). Add any new selector option that
    changes the listing request to ``_list_key``.
    """

    def __init__(self, selector: RepositorySelectorStrategy) -> None:
        self._selector = selector
        self._listed: Dict[Tuple[str, bool], List[Tuple[str, str, Dict[str, Any]]]] = {}

    @staticmethod
    def _list_key(selector: RepoListSelector, org_login: str) -> Tuple[str, bool]:
        return org_login, selector.exclude_archived

    async def select_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
        org_type: str,
        pushed_since: Optional[datetime] = None,
    ) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Return (repo_name, branch, repo_obj) tuples, listing the org at most once per key."""
        if selector.repos:
            return [
                repo
                async for repo in self._selector.select_repos(
                    selector, repo_exporter, org_login, org_type, pushed_since
                )
            ]

        key = self._list_key(selector, org_login)
        if key not in self._listed:
            self._listed[key] = [
                repo
                async for repo in self._selector.select_repos(
                    selector, repo_exporter, org_login, org_type, pushed_since
                )
            ]
        return self._listed[key]
