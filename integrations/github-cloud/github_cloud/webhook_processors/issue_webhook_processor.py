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

class IssueWebhookProcessor(AbstractWebhookProcessor):
    """Handles GitHub issue webhook events."""
    
    def __init__(self):
        self.client = init_client()
        self._supported_resource_kinds = [ObjectKind.ISSUE]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event."""
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")
        
        # Only process issue events with specific actions
        valid_actions = {"opened", "closed", "reopened", "edited", "assigned", 
                        "unassigned", "labeled", "unlabeled", "milestoned", 
                        "demilestoned", "deleted"}
        
        return event_name == "issues" and event_type in valid_actions

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
            issue = payload.get("issue", {})
            repo = payload.get("repository", {})
            
            if not issue or not repo:
                logger.warning("Missing required data in payload")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )

            issue_number = issue.get("number")
            repo_name = repo.get("name")
            
            if not issue_number or not repo_name:
                logger.warning("Missing required fields in issue data")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )

            # Handle delete events
            if action == "deleted":
                logger.info(f"Issue #{issue_number} was deleted in {repo_name}")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[issue],
                )

            # Handle create/update events
            try:
                latest_issue = await self.client.fetch_resource(
                    ObjectKind.ISSUE,
                    f"{repo_name}/{issue_number}"
                )
                
                if not latest_issue:
                    logger.warning(f"Unable to retrieve modified resource data for issue {repo_name}#{issue_number}")
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[],
                    )
                    
                logger.info(f"Successfully retrieved modified resource data for issue {repo_name}#{issue_number}")
                return WebhookEventRawResults(
                    updated_raw_results=[latest_issue],
                    deleted_raw_results=[],
                )
            except Exception as e:
                logger.error(f"Error fetching latest issue data: {e}")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )

        except Exception as e:
            logger.error(f"Error processing issue webhook event: {e}")
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
            if not payload.get("issue") or not payload.get("repository"):
                logger.warning("Missing required fields in issue webhook payload")
                return False
                
            issue = payload.get("issue", {})
            if not issue.get("number"):
                logger.warning("Missing issue number in payload")
                return False
                
            repo = payload.get("repository", {})
            if not repo.get("name"):
                logger.warning("Missing repository name in payload")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error validating issue webhook payload: {e}")
            return False
