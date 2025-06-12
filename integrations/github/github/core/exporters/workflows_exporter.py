from typing import Any, cast
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import (
    AbstractGithubExporter,
)
from github.core.options import ListWorkflowOptions, SingleWorkflowOptions
from github.helpers.utils import enrich_with_repository


class RestWorkflowExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[
        ExporterOptionsT: SingleWorkflowOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{options['repo_name']}/actions/workflows/{options['workflow_id']}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched workflow {options['workflow_id']} from {options['repo_name']}"
        )

        return response

    async def get_paginated_resources[
        ExporterOptionsT: ListWorkflowOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all workflows in repository with pagination."""

        url = f"{self.client.base_url}/repos/{self.client.organization}/{options['repo_name']}/actions/workflows"
        async for workflows in self.client.send_paginated_request(url):
            workflow_batch = cast(dict[str, Any], workflows)
            logger.info(
                f"fetched batch of {workflow_batch['total_count']} workflows from {options['repo_name']}"
            )
            batch = [
                enrich_with_repository(workflow, options["repo_name"])
                for workflow in workflow_batch["workflows"]
            ]
            yield batch
