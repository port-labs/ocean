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
        event_type = event.payload.get("action")
        event = event.headers.get("x-github-event")

        return event == "workflow_run" and event_type in WORKFLOW_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.WORKFLOW]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle workflow webhook events."""
        action = payload.get("action")
        workflow_run = payload.get("workflow_run", {})
        workflow = payload.get("workflow", {})
        repo = payload.get("repository", {})

        workflow_id = workflow["id"]
        repo_name = repo.get("name")

        logger.info(
            f"Processing workflow event: {action} for workflow {workflow_id} in {repo_name}"
        )

        client = GitHubClient.from_ocean_config()
        latest_workflow = await client.get_single_resource(
            ObjectKind.WORKFLOW, f"{repo_name}/{workflow_id}"
        )

        # Enrich workflow data with the latest run
        latest_workflow["latest_run"] = workflow_run

        return WebhookEventRawResults(
            updated_raw_results=[latest_workflow], deleted_raw_results=[]
        )
