from typing import Any, cast
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from github.clients.base_client import AbstractGithubClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListWorkflowOptions, SingleWorkflowOptions


class WorkflowRunExporter(AbstractGithubExporter[AbstractGithubClient]):
    async def get_resource[
        ExporterOptionsT: SingleWorkflowOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        endpoint = f"repos/{self.client.organization}/{options['repo']}/actions/runs/{options['resource_id']}"
        response = await self.client.send_api_request(endpoint)

        logger.info(f"Fetched workflow with identifier: {options['resource_id']}")

        return response.json()

    @cache_iterator_result()
    async def get_paginated_resources[
        ExporterOptionsT: ListWorkflowOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all workflows in repository with pagination."""

        url = f"repos/{self.client.organization}/{options['repo']}/actions/runs"
        async for workflows in self.client.send_paginated_request(url, {}):
            # Unlike almost everywhere else, the result returned by workflows is not actually an array
            # So let's do some type casting here rather than force every other method to handle a rare case
            workflow_batch = cast(dict[str, Any | list[dict[str, Any]]], workflows)
            logger.info(
                f"fetched batch of {workflow_batch['total_count']} workflow runs from repository - {options['repo']}"
            )
            yield workflow_batch["workflow_runs"]
