from typing import List
from loguru import logger
from github_cloud.helpers.utils import ObjectKind
from github_cloud.initialize_client import init_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
    EventHeaders,
)
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor

class WorkflowWebhookProcessor(AbstractWebhookProcessor):
    """Handles GitHub workflow webhook events."""
    
    def __init__(self):
        self.client = init_client()
        self._supported_resource_kinds = [ObjectKind.WORKFLOW]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event."""
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")
        
        # Process both workflow and workflow_run events
        valid_actions = {"created", "deleted", "updated", "run_started", "run_completed", "completed", "requested", "in_progress"}
        
        return event_name in ["workflow", "workflow_run"] and event_type in valid_actions

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        """Get the list of resource kinds that this processor supports.
        
        Args:
            event: The webhook event to check
            
        Returns:
            List[str]: List of supported resource kinds
        """
        return self._supported_resource_kinds

    async def get_supported_resource_kinds(self, event: WebhookEvent) -> List[str]:
        """Get the list of resource kinds that this processor supports.
        
        Args:
            event: The webhook event to check
            
        Returns:
            List[str]: List of supported resource kinds
        """
        return self._supported_resource_kinds

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the webhook event.
        
        Args:
            payload: The webhook event payload
            resource: The resource configuration
            
        Returns:
            WebhookEventRawResults: The results of processing the webhook event
        """
        return await self.process_webhook_event(payload, resource)

    async def process_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the webhook event."""
        try:
            action = payload.get("action")
            workflow = payload.get("workflow", {})
            workflow_run = payload.get("workflow_run", {})
            
            if not workflow and not workflow_run:
                logger.warning("Missing required data in payload")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )

            # Handle workflow events
            if workflow:
                workflow_id = workflow.get("id")
                workflow_name = workflow.get("name")
                
                if not workflow_id or not workflow_name:
                    logger.warning("Missing required fields in workflow data")
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[],
                    )

                # Handle delete events
                if action == "deleted":
                    logger.info(f"Workflow {workflow_name} was deleted")
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[workflow],
                    )

                # Handle create/update events
                try:
                    latest_workflow = await self.client.fetch_resource(
                        ObjectKind.WORKFLOW,
                        str(workflow_id)
                    )
                    
                    if not latest_workflow:
                        logger.warning(f"Unable to retrieve modified resource data for workflow {workflow_name}")
                        return WebhookEventRawResults(
                            updated_raw_results=[],
                            deleted_raw_results=[],
                        )
                        
                    logger.info(f"Successfully retrieved modified resource data for workflow {workflow_name}")
                    return WebhookEventRawResults(
                        updated_raw_results=[latest_workflow],
                        deleted_raw_results=[],
                    )
                except Exception as e:
                    logger.error(f"Error fetching latest workflow data: {e}")
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[],
                    )

            # Handle workflow_run events
            if workflow_run:
                workflow_id = workflow_run.get("id")
                
                if not workflow_id:
                    logger.warning("Missing required fields in workflow run data")
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[],
                    )

                try:
                    latest_workflow = await self.client.fetch_resource(
                        ObjectKind.WORKFLOW,
                        str(workflow_id)
                    )
                    
                    if not latest_workflow:
                        logger.warning(f"Unable to retrieve modified resource data for workflow run {workflow_id}")
                        return WebhookEventRawResults(
                            updated_raw_results=[],
                            deleted_raw_results=[],
                        )
                        
                    logger.info(f"Successfully retrieved modified resource data for workflow run {workflow_id}")
                    return WebhookEventRawResults(
                        updated_raw_results=[latest_workflow],
                        deleted_raw_results=[],
                    )
                except Exception as e:
                    logger.error(f"Error fetching latest workflow run data: {e}")
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[],
                    )

        except Exception as e:
            logger.error(f"Error processing workflow webhook event: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate the webhook request."""
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload."""
        try:
            # Check for either workflow or workflow_run
            if not payload.get("workflow") and not payload.get("workflow_run"):
                logger.warning("Missing required fields in workflow webhook payload")
                return False
                
            # Validate workflow payload
            if payload.get("workflow"):
                workflow = payload.get("workflow", {})
                if not workflow.get("id") or not workflow.get("name"):
                    logger.warning("Missing workflow ID or name in payload")
                    return False
                    
            # Validate workflow_run payload
            if payload.get("workflow_run"):
                workflow_run = payload.get("workflow_run", {})
                if not workflow_run.get("id"):
                    logger.warning("Missing workflow run ID in payload")
                    return False
                
            return True
        except Exception as e:
            logger.error(f"Error validating workflow webhook payload: {e}")
            return False
