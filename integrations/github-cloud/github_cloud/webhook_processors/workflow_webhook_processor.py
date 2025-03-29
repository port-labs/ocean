from loguru import logger
from github_cloud.helpers.constants import WORKFLOW_DELETE_EVENTS, WORKFLOW_UPSERT_EVENTS
from github_cloud.helpers.utils import ObjectKind
from initialize_client import init_client
from github_cloud.webhook_processors.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class WorkflowWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")

        return (event_name == "workflow" and event_type in WORKFLOW_UPSERT_EVENTS + WORKFLOW_DELETE_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.WORKFLOW]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload.get("action")
        workflow = payload.get("workflow", {})
        repo_name = payload.get("repository", {}).get("name")
        workflow_id = workflow.get("id")

        logger.info(
            f"Processing workflow event: {action} for workflow ID {workflow_id} in {repo_name}"
        )

        if action in WORKFLOW_DELETE_EVENTS:
            logger.info(f"Workflow ID {workflow_id} was deleted in {repo_name}")

            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[workflow],
            )

        client = init_client()
        latest_workflow = await client.get_single_resource(
            ObjectKind.WORKFLOW, f"{repo_name}/{workflow_id}"
        )

        logger.info(f"Successfully retrieved recent data for workflow ID {workflow_id} in {repo_name}")

        return WebhookEventRawResults(
            updated_raw_results=[latest_workflow], deleted_raw_results=[]
        )
