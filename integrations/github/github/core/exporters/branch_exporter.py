import asyncio
from typing import Any, cast
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListBranchOptions, SingleBranchOptions
from github.clients.http.rest_client import GithubRestClient
from github.helpers.utils import enrich_with_repository, parse_github_options


class RestBranchExporter(AbstractGithubExporter[GithubRestClient]):

    async def fetch_branch(
        self, repo_name: str, branch_name: str, organization: str
    ) -> RAW_ITEM:
        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/branches/{branch_name}"
        response = await self.client.send_api_request(endpoint)
        return response

    async def get_resource[
        ExporterOptionsT: SingleBranchOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        repo_name, organization, params = parse_github_options(dict(options))
        branch_name = params["branch_name"]
        protection_rules = bool(params["protection_rules"])
        repo_name = cast(str, repo_name)

        response = await self.fetch_branch(repo_name, branch_name, organization)

        if protection_rules:
            response = await self._enrich_branch_with_protection_rules(
                repo_name, response, organization
            )

        logger.info(
            f"Fetched branch: {branch_name} for repo: {repo_name} from {organization}"
        )

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListBranchOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all branches in the repository with pagination."""

        repo_name, organization, params = parse_github_options(dict(options))
        detailed = bool(params.pop("detailed"))
        protection_rules = bool(params.pop("protection_rules"))
        repo_name = cast(str, repo_name)

        async for branches in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/branches",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(branches)} branches from repository {repo_name} from {organization}"
            )
            tasks = [
                self._hydrate_branch(
                    repo_name, organization, b, detailed, protection_rules
                )
                for b in branches
            ]
            hydrated = await asyncio.gather(*tasks)

            logger.info(f"Processed {len(hydrated)} branches for '{repo_name}'.")

            yield hydrated

    async def _hydrate_branch(
        self,
        repo_name: str,
        organization: str,
        branch: dict[str, Any],
        detailed: bool,
        protection_rules: bool,
    ) -> dict[str, Any]:
        branch_name = branch["name"]

        if detailed:
            branch = await self.fetch_branch(repo_name, branch_name, organization)
            logger.debug(
                f"Added extra details for branch '{branch_name}' in repo '{repo_name}'."
            )

        if protection_rules:
            branch = await self._enrich_branch_with_protection_rules(
                repo_name, branch, organization
            )

        return enrich_with_repository(branch, repo_name)

    async def _enrich_branch_with_protection_rules(
        self, repo_name: str, branch: dict[str, Any], organization: str
    ) -> RAW_ITEM:
        """Return protection rules or None (404/403 ignored by client)."""
        branch_name = branch["name"]

        endpoint = (
            f"{self.client.base_url}/repos/"
            f"{organization}/{repo_name}/branches/{branch_name}/protection"
        )

        protection_rules = await self.client.send_api_request(endpoint)

        branch = {**branch, "__protection_rules": protection_rules}

        logger.debug(
            f"Fetched protection rules for branch '{branch_name}' in repo '{repo_name}'."
        )

        return branch
