import asyncio
from typing import Any, cast, Optional
from urllib.parse import quote

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListBranchRuleOptions, SingleBranchRuleOptions
from github.helpers.utils import (
    enrich_with_repository,
    enrich_with_organization,
    parse_github_options,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

BATCH_CONCURRENCY_LIMIT = 10


class RestBranchRuleExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleBranchRuleOptions
    ](self, options: ExporterOptionsT) -> Optional[RAW_ITEM]:
        repo_name, organization, params = parse_github_options(dict(options))
        branch_name = params["branch_name"]
        repo_name = cast(str, repo_name)
        repo = params.pop("repo", None)

        rules = await self._fetch_branch_rules(organization, repo_name, branch_name)
        if not rules:
            return None

        enriched = [
            self._enrich_rule(rule, organization, repo_name, branch_name, repo)
            for rule in rules
        ]
        return enriched  # type: ignore[return-value]

    async def get_paginated_resources[
        ExporterOptionsT: ListBranchRuleOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all branch rules for the repository's branches."""
        repo_name, organization, params = parse_github_options(dict(options))
        repo_name = cast(str, repo_name)
        repo = params.pop("repo", None)
        branch_names = params.pop("branch_names", []) or []
        default_branch_only = bool(params.pop("default_branch_only", True))

        if default_branch_only:
            branch_names = [repo["default_branch"]]
        elif not branch_names:
            branch_names = await self._list_branch_names(organization, repo_name)

        semaphore = asyncio.Semaphore(BATCH_CONCURRENCY_LIMIT)

        async def _fetch_for_branch(branch: str) -> list[dict[str, Any]]:
            async with semaphore:
                rules = await self._fetch_branch_rules(
                    organization, repo_name, branch
                )
                return [
                    self._enrich_rule(rule, organization, repo_name, branch, repo)
                    for rule in rules
                ]

        tasks = [_fetch_for_branch(b) for b in branch_names if b]
        results = await asyncio.gather(*tasks)

        all_rules = [rule for branch_rules in results for rule in branch_rules]
        if all_rules:
            logger.info(
                f"Fetched {len(all_rules)} branch rules across {len(branch_names)} "
                f"branch(es) in {repo_name} from {organization}"
            )
            yield all_rules

    async def _fetch_branch_rules(
        self, organization: str, repo_name: str, branch_name: str
    ) -> list[dict[str, Any]]:
        endpoint = (
            f"{self.client.base_url}/repos/"
            f"{organization}/{repo_name}/rules/branches/{quote(branch_name)}"
        )
        all_rules: list[dict[str, Any]] = []
        async for page in self.client.send_paginated_request(endpoint):
            all_rules.extend(page)

        logger.debug(
            f"Fetched {len(all_rules)} rules for branch '{branch_name}' "
            f"in repo '{repo_name}' from {organization}"
        )
        return all_rules

    async def _list_branch_names(
        self, organization: str, repo_name: str
    ) -> list[str]:
        endpoint = (
            f"{self.client.base_url}/repos/{organization}/{repo_name}/branches"
        )
        names: list[str] = []
        async for branches in self.client.send_paginated_request(endpoint):
            names.extend(b["name"] for b in branches)
        return names

    def _enrich_rule(
        self,
        rule: dict[str, Any],
        organization: str,
        repo_name: str,
        branch_name: str,
        repo: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        rule["__branch"] = branch_name
        enriched = enrich_with_organization(
            enrich_with_repository(rule, repo_name, repo=repo), organization
        )
        return enriched
