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

    ``changed_since`` (optional) keeps only repositories changed since then.
    """

    def __init__(self, repo_type: str):
        self.repo_type = repo_type

    async def select_repos(
        self,
        selector: RepoListSelector,
        repo_exporter: AbstractGithubExporter[Any],
        org_login: str,
        org_type: str,
        changed_since: Optional[RepositoryChange] = None,
    ) -> RepoSelection:
        """Repositories the selector resolves to, optionally only those changed since ``changed_since``."""
        if selector.repos:
            async for repo in self._explicit_repos(selector, repo_exporter, org_login):
                if _changed_since(repo[2], changed_since):
                    yield repo
                else:
                    logger.debug(f"Skipping unchanged repository {repo[0]}")
            return
        options = self._list_options(selector, org_login, org_type)
        options["changed_since"] = changed_since
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


def _changed_since(
    repo: Dict[str, Any], changed_since: Optional[RepositoryChange]
) -> bool:
    """Whether ``repo`` passes the optional ``changed_since`` filter (always, without one)."""
    if changed_since is None:
        return True
    return changed_since.matches(repo.get(changed_since.field.value))
