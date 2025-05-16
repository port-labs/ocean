from typing import Any, cast
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger

from github.core.exporters.abstract_exporter import (
    AbstractGithubExporter,
)
from github.core.options import ListWorkflowOptions, SingleWorkflowOptions
from github.clients.base_client import AbstractGithubClient


class WorkflowExporter(AbstractGithubExporter[AbstractGithubClient]):
    async def get_resource[
        OptionT: SingleWorkflowOptions
    ](self, options: OptionT) -> RAW_ITEM:
        endpoint = f"repos/{self.client.organization}/{options['repo']}/actions/workflows/{options['resource_id']}"
        response = await self.client.send_api_request(endpoint)

        logger.info(f"Fetched workflow with identifier: {options['resource_id']}")

        return response.json()

    @cache_iterator_result()
    async def get_paginated_resources[
        OptionT: ListWorkflowOptions
    ](self, options: OptionT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all workflows in repository with pagination."""

        url = f"repos/{self.client.organization}/{options['repo']}/actions/workflows"
        async for workflows in self.client.send_paginated_request(url, {}):
            # Unlike almost everywhere else, the result returned by workflows is not actually an array
            # So let's do some type casting here rather than force every other method to handle a rare case
            workflow_batch = cast(dict[str, Any | list[dict[str, Any]]], workflows)
            logger.info(
                f"fetched batch of {workflow_batch['total_count']} workflows from repository - {options['repo']}"
            )
            batch = [
                {**workflow, "repo": options["repo"]}
                for workflow in workflow_batch["workflows"]
            ]
            yield batch
