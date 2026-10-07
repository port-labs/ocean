from datetime import datetime
from typing import Any, cast, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import (
    AbstractGithubExporter,
)
from github.core.options import ListWorkflowOptions, SingleWorkflowOptions
from github.helpers.utils import enrich_with_repository, enrich_with_organization


class RestWorkflowExporter(AbstractGithubExporter[GithubRestClient]):
    async def has_workflow_changes_since(
        self, organization: str, repo_name: str, cursor: datetime | None
    ) -> bool:
        """Check if repo has commits touching .github/workflows since cursor."""
        if not cursor:
            return True

        since_date = cursor.isoformat()
        url = f"{self.client.base_url}/repos/{organization}/{repo_name}/commits"
        params = {"path": ".github/workflows", "since": since_date, "per_page": 1}

        async for commits_page in self.client.send_paginated_request(url, params):
            commits = (
                commits_page
                if isinstance(commits_page, list)
                else commits_page.get("items", [])
            )
            return bool(commits)

        return False

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
