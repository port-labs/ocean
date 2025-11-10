from abc import ABC, abstractmethod
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


from github.core.options import (
    ListOrganizationOptions,
    ListRepositoryOptions,
)
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import get_repository_metadata

if TYPE_CHECKING:
    from integration import RepositoryBranchMapping


class RepoListSelector(Protocol):
    """Minimal selector interface exposing optional repos list."""

    repos: Optional[List["RepositoryBranchMapping"]]


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
            repo_obj = await get_repository_metadata(
                repo_exporter.client, org_login, repo_sel.name
            )
            if not repo_obj:
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
            if not batch or not any(batch):
                continue
            for org in batch:
                org_login = org["login"]
                yield org_login
