from typing import List, Optional, Dict, Any
from loguru import logger
from github_cloud.helpers.utils import ObjectKind
from github_cloud.helpers.constants import ISSUE_DELETE_EVENTS, ISSUE_UPSERT_EVENTS
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
from github_cloud.webhook_processors.events import IssueEvent

class IssueEventPipeline(BaseEventPipeline[IssueEvent]):
    """Pipeline for processing GitHub issue events."""
    
    def __init__(self):
        super().__init__()
        self.client = init_client()

    def _extract_event_data(self, payload: EventPayload) -> Optional[IssueEvent]:
        """Extract and validate event data from the payload."""
        try:
            action = payload.get("action")
            issue = payload.get("issue", {})
            repo = payload.get("repository", {})
            
            if not self._validate_required_fields(issue, ["number"]) or not repo:
                logger.warning("Missing required data in payload")
                return None
                
            return IssueEvent(
                action=action,
                issue_number=issue.get("number"),
                repo_name=repo.get("name"),
                issue_data=issue,
                repository_data=repo
            )
        except Exception as e:
            logger.error(f"Failed to extract event data: {e}")
            return None

    async def _handle_delete(self, event: IssueEvent) -> WebhookEventRawResults:
        """Handle issue deletion events."""
        logger.info(f"Issue #{event.issue_number} was deleted in {event.repo_name}")
        return WebhookEventRawResults(
            modified_resources=[],
            removed_resources=[event.issue_data],
        )

    async def _handle_upsert(self, event: IssueEvent) -> WebhookEventRawResults:
        """Handle issue creation/update events."""
        try:
            latest_issue = await self.client.fetch_resource(
                ObjectKind.ISSUE,
                f"{event.repo_name}/{event.issue_number}"
            )
            
            if not latest_issue:
                logger.warning(f"Unable to retrieve modified resource data for issue {event.repo_name}#{event.issue_number}")
                return WebhookEventRawResults(
                    modified_resources=[],
                    removed_resources=[],
                )
                
            logger.info(f"Successfully retrieved modified resource data for issue {event.repo_name}#{event.issue_number}")
            return WebhookEventRawResults(
                modified_resources=[latest_issue],
                removed_resources=[],
            )
        except Exception as e:
            logger.error(f"Error handling issue upsert: {e}")
            return WebhookEventRawResults(
                modified_resources=[],
                removed_resources=[],
            )

    def _determine_handler(self, event: IssueEvent) -> str:
        """Determine which handler to use based on the event type."""
        if event.action in ISSUE_DELETE_EVENTS:
            return 'delete'
        elif event.action in ISSUE_UPSERT_EVENTS:
            return 'upsert'
        return 'default'

class IssueWebhookProcessor(AbstractWebhookProcessor):
    """Main webhook processor for GitHub issues."""
    
    def __init__(self):
        super().__init__()
        self.pipeline = IssueEventPipeline()

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event."""
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")
        return (
            event_name == "issues"
            and event_type in ISSUE_UPSERT_EVENTS + ISSUE_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        """Get the resource kinds this processor handles."""
        return [ObjectKind.ISSUE]

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
            if not payload.get("issue") or not payload.get("repository"):
                logger.warning("Missing required fields in issue webhook payload")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating issue webhook payload: {e}")
            return False
