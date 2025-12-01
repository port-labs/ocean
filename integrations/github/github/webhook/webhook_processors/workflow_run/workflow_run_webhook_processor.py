from typing import cast
from loguru import logger
from github.core.exporters.workflow_runs_exporter import RestWorkflowRunExporter
from github.core.options import SingleWorkflowRunOptions
from github.webhook.events import WORKFLOW_DELETE_EVENTS
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.workflow_run.base_workflow_run_webhook_processor import (
    BaseWorkflowRunWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEventRawResults,
)

from integration import GithubRepoSearchConfig


class WorkflowRunWebhookProcessor(BaseWorkflowRunWebhookProcessor):
    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        repo = payload["repository"]
        workflow_run = payload["workflow_run"]
        organization = payload["organization"]["login"]

        logger.info(
            f"Processing workflow run event: {action} of organization: {organization}"
        )
        config = cast(GithubRepoSearchConfig, resource_config)

        if config.selector.repo_search is not None:
            logger.info(
                "search query is configured for this kind, checking if repository is in matched results."
            )
            if await self.repo_in_search(payload, resource_config) is None:
                logger.info(
                    "Repository is not matched by search query, no actions will be performed."
                )
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

        if action in WORKFLOW_DELETE_EVENTS:
            logger.info(
                f"Workflow run {workflow_run['name']} was deleted from organization: {organization}"
            )

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[workflow_run]
            )

        exporter = RestWorkflowRunExporter(create_github_client())
        options = SingleWorkflowRunOptions(
            organization=organization, repo_name=repo["name"], run_id=workflow_run["id"]
        )

        data_to_upsert = await exporter.get_resource(options)
        logger.info(
            f"Workflow run {data_to_upsert['name']} of organization: {organization} was upserted"
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
