from typing import List, Optional, Dict, Any
from loguru import logger
from github_cloud.helpers.utils import ObjectKind
from github_cloud.helpers.constants import WORKFLOW_DELETE_EVENTS, WORKFLOW_UPSERT_EVENTS
from github_cloud.initialize_client import init_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
    EventHeaders,
)
from github_cloud.webhook_processors.abstract_webhook_processor import AbstractWebhookProcessor
from github_cloud.webhook_processors.base_pipeline import BaseEventPipeline
from github_cloud.webhook_processors.events import WorkflowEvent

class WorkflowEventPipeline(BaseEventPipeline[WorkflowEvent]):
    """Pipeline for processing GitHub workflow events."""
    
    def __init__(self):
        super().__init__()
        self.client = init_client()

    def _extract_event_data(self, payload: EventPayload) -> Optional[WorkflowEvent]:
        """Extract and validate event data from the payload."""
        try:
            action = payload.get("action")
            workflow = payload.get("workflow", {})
            repo = payload.get("repository", {})
            
            if not self._validate_required_fields(workflow, ["name"]) or not repo:
                logger.warning("Missing required data in payload")
                return None
                
            return WorkflowEvent(
                action=action,
                workflow_name=workflow.get("name"),
                repo_name=repo.get("name"),
                workflow_data=workflow,
                repository_data=repo
            )
        except Exception as e:
            logger.error(f"Failed to extract event data: {e}")
            return None

    async def _handle_delete(self, event: WorkflowEvent) -> WebhookEventRawResults:
        """Handle workflow deletion events."""
        logger.info(f"Workflow {event.workflow_name} was deleted in {event.repo_name}")
        return WebhookEventRawResults(
            modified_resources=[],
            removed_resources=[event.workflow_data],
        )

    async def _handle_upsert(self, event: WorkflowEvent) -> WebhookEventRawResults:
        """Handle workflow creation/update events."""
        try:
            latest_workflow = await self.client.fetch_resource(
                ObjectKind.WORKFLOW,
                f"{event.repo_name}/{event.workflow_name}"
            )
            
            if not latest_workflow:
                logger.warning(f"Unable to retrieve modified resource data for workflow {event.repo_name}/{event.workflow_name}")
                return WebhookEventRawResults(
                    modified_resources=[],
                    removed_resources=[],
                )
                
            logger.info(f"Successfully retrieved modified resource data for workflow {event.repo_name}/{event.workflow_name}")
            return WebhookEventRawResults(
                modified_resources=[latest_workflow],
                removed_resources=[],
            )
        except Exception as e:
            logger.error(f"Error handling workflow upsert: {e}")
            return WebhookEventRawResults(
                modified_resources=[],
                removed_resources=[],
            )

    def _determine_handler(self, event: WorkflowEvent) -> str:
        """Determine which handler to use based on the event type."""
        if event.action in WORKFLOW_DELETE_EVENTS:
            return 'delete'
        elif event.action in WORKFLOW_UPSERT_EVENTS:
            return 'upsert'
        return 'default'

class WorkflowWebhookProcessor(AbstractWebhookProcessor):
    """Main webhook processor for GitHub workflows."""
    
    def __init__(self):
        super().__init__()
        self.pipeline = WorkflowEventPipeline()

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event."""
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")
        return (
            event_name == "workflow"
            and event_type in WORKFLOW_UPSERT_EVENTS + WORKFLOW_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        """Get the resource kinds this processor handles."""
        return [ObjectKind.WORKFLOW]

    async def process_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the webhook event using the pipeline."""
        return await self.pipeline.process(payload, resource_config)

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate the webhook request."""
        # GitHub webhooks are authenticated via the webhook secret
        # This is handled at the application level
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload."""
        try:
            # Check for required fields
            if not payload.get("workflow") or not payload.get("repository"):
                logger.warning("Missing required fields in workflow webhook payload")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating workflow webhook payload: {e}")
            return False
