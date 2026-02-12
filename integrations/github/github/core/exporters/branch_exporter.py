import asyncio
from typing import Any, cast, Optional
from urllib.parse import quote
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListBranchOptions, SingleBranchOptions
from github.clients.http.rest_client import GithubRestClient
from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
    enrich_with_organization,
)

BATCH_CONCURRENCY_LIMIT = 10


class RestBranchExporter(AbstractGithubExporter[GithubRestClient]):

    async def fetch_branch(
        self, repo_name: str, branch_name: str, organization: str
    ) -> RAW_ITEM:
        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/branches/{quote(branch_name)}"
        response = await self.client.send_api_request(endpoint)
        return response

    async def get_resource[
        ExporterOptionsT: SingleBranchOptions
    ](self, options: ExporterOptionsT) -> Optional[RAW_ITEM]:

        repo_name, organization, params = parse_github_options(dict(options))
        branch_name = params["branch_name"]
        protection_rules = bool(params["protection_rules"])
        repo_name = cast(str, repo_name)
        repo = params.pop("repo")

        response = await self.fetch_branch(repo_name, branch_name, organization)
        if not response:
            logger.warning(
                f"No branch found with name: {branch_name} in repository: {repo_name} from {organization}"
            )
            return None

        if protection_rules:
            response = await self._enrich_branch_with_protection_rules(
                repo_name, response, organization
            )

        logger.info(
            f"Fetched branch: {branch_name} for repo: {repo_name} from {organization}"
        )

        return enrich_with_organization(
            enrich_with_repository(response, repo_name, repo=repo), organization
        )

    async def get_paginated_resources[
        ExporterOptionsT: ListBranchOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all branches in the repository with pagination."""

        repo_name, organization, params = parse_github_options(dict(options))
        detailed = bool(params.pop("detailed"))
        protection_rules = bool(params.pop("protection_rules"))
        repo_name = cast(str, repo_name)
        repo = params.pop("repo")
        branch_names = params.pop("branch_names", [])
        default_branch_only = bool(params.pop("default_branch_only", False))

        if default_branch_only:
            branch_names = [repo["default_branch"]]

        is_explicit = bool(branch_names)
        if branch_names:

            async def _explicit_branches() -> ASYNC_GENERATOR_RESYNC_TYPE:
                yield [{"name": name} for name in branch_names if name]

            branches_iterator = _explicit_branches()
        else:
            branches_iterator = self.client.send_paginated_request(
                f"{self.client.base_url}/repos/{organization}/{repo_name}/branches",
                params,
            )

        async for branches in branches_iterator:
            logger.info(
                f"Fetched batch of {len(branches)} branches from repository {repo_name} from {organization}"
            )

            batch_concurrency_limit = asyncio.Semaphore(BATCH_CONCURRENCY_LIMIT)

            tasks = [
                self._run_branch_hydration(
                    repo,
                    organization,
                    branch,
                    is_explicit or detailed,
                    protection_rules,
                    batch_concurrency_limit,
                )
                for branch in branches
            ]

            hydrated = await asyncio.gather(*tasks)
            yield [branch for branch in hydrated if branch is not None]

    async def _run_branch_hydration(
        self,
        repo: dict[str, Any],
        organization: str,
        branch: dict[str, Any],
        detailed: bool,
        protection_rules: bool,
        batch_concurrency_limit: asyncio.Semaphore,
    ) -> Optional[dict[str, Any]]:
        async with batch_concurrency_limit:
            return await self._hydrate_branch(
                repo,
                organization,
                branch,
                detailed,
                protection_rules,
            )

    async def _hydrate_branch(
        self,
        repo: dict[str, Any],
        organization: str,
        branch: dict[str, Any],
        detailed: bool,
        protection_rules: bool,
    ) -> Optional[dict[str, Any]]:
        repo_name = repo["name"]
        branch_name = branch["name"]

        if detailed:
            branch = await self.fetch_branch(repo_name, branch_name, organization)
            if not branch:
                logger.warning(
                    f"No branch found with name: {branch_name} in repository: {repo_name} from {organization}"
                )
                return None

            logger.info(
                f"Added extra details for branch '{branch_name}' in repo '{repo_name}'."
            )

        if protection_rules:
            branch = await self._enrich_branch_with_protection_rules(
                repo_name, branch, organization
            )

        return enrich_with_organization(
            enrich_with_repository(branch, repo_name, repo=repo), organization
        )

    async def _enrich_branch_with_protection_rules(
        self, repo_name: str, branch: dict[str, Any], organization: str
    ) -> RAW_ITEM:
        """Return protection rules or None (404/403 ignored by client)."""
        branch_name = branch["name"]

        endpoint = (
            f"{self.client.base_url}/repos/"
            f"{organization}/{repo_name}/branches/{quote(branch_name)}/protection"
        )

        protection_rules = await self.client.send_api_request(endpoint)
        branch["__protection_rules"] = protection_rules

        logger.debug(
            f"Fetched protection rules for branch '{branch_name}' in repo '{repo_name}'."
        )

        return branch
