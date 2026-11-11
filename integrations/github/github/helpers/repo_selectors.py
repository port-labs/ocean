from typing import (
    Any,
    AsyncIterator,
    Callable,
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
from github.helpers.repository_change import RepositoryChange
from github.helpers.utils import get_repository_metadata

if TYPE_CHECKING:
    from integration import RepositoryBranchMapping


class RepoListSelector(Protocol):
    """Minimal selector interface exposing optional repos list."""

    repos: Optional[List["RepositoryBranchMapping"]]
    exclude_archived: bool


RepoSelection = AsyncIterator[Tuple[str, str, Dict[str, Any]]]


class RepositorySelector:
    """Resolve the repositories a selector points at, as (repo_name, branch, repo_obj).

    - Explicit ``repos`` on the selector: fetch each one's metadata; the branch
      falls back to the default branch. Explicit repos are always included
      regardless of ``exclude_archived`` - the same precedent already applies
      to ``repo_search``/``search_params``, which are never consulted here.
    - No explicit repos: list every repository of ``repo_type`` in the org.

    ``select_repos`` returns every selected repo; ``select_repos_changed_since``
    only those changed since ``change``.
    """

    def __init__(self, repo_type: str):
        self.repo_type = repo_type

    async def select_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
        org_type: str,
    ) -> RepoSelection:
        """Every repository the selector resolves to."""
        if selector.repos:
            async for repo in self._explicit_repos(selector, repo_exporter, org_login):
                yield repo
            return
        options = self._list_options(selector, org_login, org_type)
        async for repo in self._list_repos(repo_exporter, org_login, options):
            yield repo

    async def select_repos_changed_since(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
        org_type: str,
        change: RepositoryChange,
    ) -> RepoSelection:
        """Only the repositories the selector resolves to that changed since ``change``."""
        if selector.repos:
            async for repo in self._explicit_repos(selector, repo_exporter, org_login):
                if change.matches(repo[2].get(change.field.value)):
                    yield repo
                else:
                    logger.debug(f"Skipping unchanged repository {repo[0]}")
            return
        options = self._list_options(selector, org_login, org_type)
        options["changed_since"] = change
        async for repo in self._list_repos(repo_exporter, org_login, options):
            yield repo

    def _list_options(
        self, selector: RepoListSelector, org_login: str, org_type: str
    ) -> ListRepositoryOptions:
        return ListRepositoryOptions(
            organization=org_login,
            organization_type=org_type,
            type=self.repo_type,
            exclude_archived=selector.exclude_archived,
        )

    async def _list_repos(
        self,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
        options: ListRepositoryOptions,
    ) -> RepoSelection:
        logger.info(f"Fetching all '{self.repo_type}' repositories from '{org_login}'.")
        async for batch in repo_exporter.get_paginated_resources(options):
            for repo in batch:
                yield repo["name"], repo["default_branch"], repo

    async def _explicit_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
    ) -> RepoSelection:
        for repo_sel in selector.repos or []:
            repo_obj = await get_repository_metadata(
                repo_exporter.client, org_login, repo_sel.name
            )
            if not repo_obj:
                logger.warning(f"Repository {repo_sel.name} not found in {org_login}")
                continue
            yield repo_sel.name, repo_sel.branch or repo_obj["default_branch"], repo_obj


# A bound ``select_repos`` / ``select_repos_changed_since`` (change already applied).
SelectRepos = Callable[
    [RepoListSelector, AbstractGithubExporter[Any], str, str], RepoSelection
]
