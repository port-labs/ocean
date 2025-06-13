from typing import Any, cast
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListWorkflowRunOptions, SingleWorkflowRunOptions


class RestWorkflowRunExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[
        ExporterOptionsT: SingleWorkflowRunOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{options['repo_name']}/actions/runs/{options['run_id']}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched workflow run {options['run_id']} from {options['repo_name']}"
        )

        return response

    async def get_paginated_resources[
        ExporterOptionsT: ListWorkflowRunOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all workflows in repository with pagination."""

        url = f"{self.client.base_url}/repos/{self.client.organization}/{options['repo_name']}/actions/workflows/{options['workflow_id']}/runs"
        fetched_batch = 0

        async for workflows in self.client.send_paginated_request(url):
            workflow_batch = cast(dict[str, Any], workflows)
            logger.info(
                f"Fetched batch of {workflow_batch['total_count']} workflow runs from {options['repo_name']} "
                f"for workflow {options['workflow_id']}"
            )
            yield workflow_batch["workflow_runs"]

            fetched_batch = fetched_batch + workflow_batch["total_count"]
            if fetched_batch >= options["max_runs"]:
                logger.info(
                    f"Reached maximum limit of {options['max_runs']} workflow runs"
                    f"for workflow {options['workflow_id']} in {options['repo_name']}"
                )
                return
