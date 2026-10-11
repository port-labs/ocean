from typing import Any, cast, Optional
from datetime import datetime
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import (
    AbstractGithubExporter,
)
from github.core.options import ListWorkflowOptions, SingleWorkflowOptions
from github.helpers.utils import enrich_with_repository, enrich_with_organization


class RestWorkflowExporter(AbstractGithubExporter[GithubRestClient]):
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
        """Get all workflows in repository with pagination.

        For incremental sync, filters workflows by updated_at >= updated_since.
        """

        organization = options["organization"]
        repo_name = options["repo_name"]
        url = f"{self.client.base_url}/repos/{organization}/{options['repo_name']}/actions/workflows"
        updated_since = options.get("updated_since")

        async for workflows in self.client.send_paginated_request(url):
            workflow_batch = cast(dict[str, Any], workflows)
            logger.info(
                f"Fetched batch of {len(workflow_batch['workflows'])} workflows from {repo_name} from {organization}"
            )

            batch = []
            for workflow in workflow_batch["workflows"]:
                # Filter by updated_since if provided (incremental sync)
                if updated_since:
                    workflow_updated_at_str = workflow.get("updated_at")
                    if workflow_updated_at_str:
                        try:
                            workflow_updated_at = datetime.fromisoformat(
                                workflow_updated_at_str.replace('Z', '+00:00')
                            )
                            if workflow_updated_at < updated_since:
                                continue
                        except (ValueError, AttributeError):
                            pass

                enriched_workflow = enrich_with_organization(
                    enrich_with_repository(workflow, repo_name), organization
                )
                batch.append(enriched_workflow)

            if batch:
                logger.info(
                    f"Incremental sync filtered {len(workflow_batch['workflows'])} workflows to {len(batch)} for {repo_name} from {organization}"
                )
                yield batch
