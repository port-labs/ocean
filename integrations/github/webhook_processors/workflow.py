from loguru import logger
from client import GitHubClient
from consts import WORKFLOW_EVENTS
from helpers.utils import ObjectKind
from webhook_processors.abstract import GitHubAbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

class WorkflowWebhookProcessor(GitHubAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("action") in WORKFLOW_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.WORKFLOW]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = GitHubClient.from_ocean_config()
        workflow_run = payload.get("workflow_run", {})
        workflow = workflow_run.get("workflow", {})
        repo = payload.get("repository", {})

        logger.info(f"Got workflow run event for {workflow.get('name')}")
        
        # Get the complete workflow data
        async for workflows in client.get_workflows(repo["name"]):
            for wf in workflows:
                if wf["id"] == workflow["id"]:
                    # Enrich with repository and latest run
                    wf["repository"] = repo
                    wf["latest_run"] = workflow_run
                    return WebhookEventRawResults(
                        updated_raw_results=[wf],
                        deleted_raw_results=[],
                    )

        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        ) 