from typing import Any, cast
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListWorkflowRunOptions, SingleWorkflowRunOptions


class RestWorkflowRunExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[ExporterOptionsT: SingleWorkflowRunOptions](
        self, options: ExporterOptionsT
    ) -> RAW_ITEM:
        endpoint = f"repos/{self.client.organization}/{options['repo']}/actions/runs/{options['resource_id']}"
        response = await self.client.send_api_request(endpoint)

        logger.info(f"Fetched workflow with identifier: {options['resource_id']}")

        return response.json()

    async def get_paginated_resources[ExporterOptionsT: ListWorkflowRunOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all workflows in repository with pagination."""

        url = f"repos/{self.client.organization}/{options['repo']}/actions/runs"
        async for workflows in self.client.send_paginated_request(url):
            workflow_batch = cast(dict[str, Any], workflows)
            logger.info(
                f"fetched batch of {workflow_batch['total_count']} workflow runs from repository - {options['repo']}"
            )
            yield workflow_batch["workflow_runs"]
