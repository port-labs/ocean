from datetime import datetime
from typing import Any, cast, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy
from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import (
    AbstractGithubExporter,
)
from github.core.options import ListWorkflowOptions, SingleWorkflowOptions
from github.helpers.utils import enrich_with_repository, enrich_with_organization

COMMITS_SINCE_STRATEGY = ServerSideTimestampStrategy(param_key="since")


def extract_repo_names_from_commits(commits: list[dict[str, Any]]) -> set[str]:
    """Extract unique repository names from commits response."""
    repo_names = set()
    for commit in commits:
        if isinstance(commit, dict) and "repository" in commit:
            repo_data = commit.get("repository", {})
            if isinstance(repo_data, dict):
                repo_name = repo_data.get("name")
                if repo_name:
                    repo_names.add(repo_name)
    return repo_names


class RestWorkflowExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_changed_repo_names(
        self, organization: str, cursor: datetime | None
    ) -> set[str]:
        """Get repository names with commits touching .github/workflows since cursor."""
        if not cursor:
            return set()

        changed_repos: set[str] = set()
        params = {
            **COMMITS_SINCE_STRATEGY.build_params(cursor),
            "path": ".github/workflows",
        }
        url = f"{self.client.base_url}/repos/{organization}/commits"

        async for commits_page in self.client.send_paginated_request(url, params):
            repo_names = extract_repo_names_from_commits(commits_page)
            changed_repos.update(repo_names)

        logger.info(
            f"Found {len(changed_repos)} repositories with workflow changes in {organization}"
        )
        return changed_repos

    async def get_resource[ExporterOptionsT: SingleWorkflowOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:
        organization = options["organization"]
        endpoint = f"{self.client.base_url}/repos/{organization}/{options['repo_name']}/actions/workflows/{options['workflow_id']}"

        response = await self.client.send_api_request(endpoint)
        if not response:
            logger.warning(
                f"No workflow found with id: {options['workflow_id']} in repository: {options['repo_name']} from {organization}"
            )
            return None

        workflow = enrich_with_organization(
            enrich_with_repository(response, options["repo_name"]), organization
        )
        logger.info(
            f"Fetched workflow {options['workflow_id']} from {options['repo_name']} from {organization}"
        )

        return workflow

    async def get_paginated_resources[ExporterOptionsT: ListWorkflowOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all workflows in repository with pagination."""

        organization = options["organization"]
        repo_name = options["repo_name"]
        url = f"{self.client.base_url}/repos/{organization}/{options['repo_name']}/actions/workflows"

        async for workflows in self.client.send_paginated_request(url):
            workflow_batch = cast(dict[str, Any], workflows)
            logger.info(
                f"Fetched batch of {len(workflow_batch['workflows'])} workflows from {repo_name} from {organization}"
            )
            batch = [
                enrich_with_organization(
                    enrich_with_repository(workflow, repo_name), organization
                )
                for workflow in workflow_batch["workflows"]
            ]
            yield batch
