from typing import Any, cast, Optional
from loguru import logger

from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListWorkflowRunOptions, SingleWorkflowRunOptions
from github.helpers.utils import (
    enrich_with_organization,
    enrich_with_repository,
    parse_github_options,
)

WORKFLOW_RUN_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="created",
    date_format="%Y-%m-%dT%H:%M:%SZ",
    value_prefix=">=",
)


def build_workflow_run_params(options: ListWorkflowRunOptions) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if status := options.get("status"):
        params["status"] = status
    if created := options.get("created"):
        params["created"] = created
    return params


class RestWorkflowRunExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[ExporterOptionsT: SingleWorkflowRunOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:
        organization = options["organization"]
        repo_name = options["repo_name"]
        run_id = options["run_id"]
        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/actions/runs/{run_id}"
        response = await self.client.send_api_request(endpoint)
        if not response:
            logger.warning(
                f"No workflow run found with id: {run_id} in {repo_name} from {organization}"
            )
            return None

        logger.info(
            f"Fetched workflow run {run_id} from {repo_name} from {organization}"
        )

        return enrich_with_organization(
            enrich_with_repository(response, repo_name), organization
        )

    async def get_paginated_resources[ExporterOptionsT: ListWorkflowRunOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all workflows in repository with pagination."""
        repo_name, organization, params = parse_github_options(dict(options))
        repo = cast(str, repo_name)
        incremental_cursor = params.pop("incremental_cursor", None)
        if incremental_cursor is not None:
            params.update(WORKFLOW_RUN_INCREMENTAL.build_params(incremental_cursor))
        workflow_id = params["workflow_id"]
        max_runs = cast(int, params["max_runs"])

        url = f"{self.client.base_url}/repos/{organization}/{repo}/actions/workflows/{workflow_id}/runs"
        fetched_batch = 0

        async for workflows in self.client.send_paginated_request(
            url, build_workflow_run_params(cast(ListWorkflowRunOptions, params))
        ):
            workflow_batch = cast(dict[str, Any], workflows)
            workflow_runs = workflow_batch["workflow_runs"]

            logger.info(
                f"Fetched batch of {len(workflow_runs)} workflow runs from {repo} "
                f"for workflow {workflow_id} from {organization}"
            )
            batch = [
                enrich_with_organization(
                    enrich_with_repository(workflow_run, repo), organization
                )
                for workflow_run in workflow_runs
            ]
            yield batch

            fetched_batch = fetched_batch + len(workflow_runs)
            if fetched_batch >= max_runs:
                logger.info(
                    f"Reached maximum limit of {max_runs} workflow runs"
                    f"for workflow {workflow_id} in {repo} from {organization}"
                )
                return
