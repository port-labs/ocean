from typing import List, Optional, Dict, Any
from loguru import logger
from github_cloud.helpers.utils import ObjectKind
from github_cloud.helpers.constants import PR_DELETE_EVENTS, PR_UPSERT_EVENTS
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
from github_cloud.webhook_processors.events import PullRequestEvent

class PullRequestEventPipeline(BaseEventPipeline[PullRequestEvent]):
    """Pipeline for processing GitHub pull request events."""
    
    def __init__(self):
        super().__init__()
        self.client = init_client()

    def _extract_event_data(self, payload: EventPayload) -> Optional[PullRequestEvent]:
        """Extract and validate event data from the payload."""
        try:
            action = payload.get("action")
            pull_request = payload.get("pull_request", {})
            repo = payload.get("repository", {})
            
            if not self._validate_required_fields(pull_request, ["number"]) or not repo:
                logger.warning("Missing required data in payload")
                return None
                
            return PullRequestEvent(
                action=action,
                pr_number=pull_request.get("number"),
                repo_name=repo.get("name"),
                pr_data=pull_request,
                repository_data=repo
            )
        except Exception as e:
            logger.error(f"Failed to extract event data: {e}")
            return None

    async def _handle_delete(self, event: PullRequestEvent) -> WebhookEventRawResults:
        """Handle pull request deletion events."""
        logger.info(f"Pull request #{event.pr_number} was deleted in {event.repo_name}")
        return WebhookEventRawResults(
            modified_resources=[],
            removed_resources=[event.pr_data],
        )

    async def _handle_upsert(self, event: PullRequestEvent) -> WebhookEventRawResults:
        """Handle pull request creation/update events."""
        try:
            latest_pr = await self.client.fetch_resource(
                ObjectKind.PULL_REQUEST,
                f"{event.repo_name}/{event.pr_number}"
            )
            
            if not latest_pr:
                logger.warning(f"Unable to retrieve modified resource data for pull request {event.repo_name}#{event.pr_number}")
                return WebhookEventRawResults(
                    modified_resources=[],
                    removed_resources=[],
                )
                
            logger.info(f"Successfully retrieved modified resource data for pull request {event.repo_name}#{event.pr_number}")
            return WebhookEventRawResults(
                modified_resources=[latest_pr],
                removed_resources=[],
            )
        except Exception as e:
            logger.error(f"Error handling pull request upsert: {e}")
            return WebhookEventRawResults(
                modified_resources=[],
                removed_resources=[],
            )

    def _determine_handler(self, event: PullRequestEvent) -> str:
        """Determine which handler to use based on the event type."""
        if event.action in PR_DELETE_EVENTS:
            return 'delete'
        elif event.action in PR_UPSERT_EVENTS:
            return 'upsert'
        return 'default'

class PullRequestWebhookProcessor(AbstractWebhookProcessor):
    """Main webhook processor for GitHub pull requests."""
    
    def __init__(self):
        super().__init__()
        self.pipeline = PullRequestEventPipeline()

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event."""
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")
        return (
            event_name == "pull_request"
            and event_type in PR_UPSERT_EVENTS + PR_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        """Get the resource kinds this processor handles."""
        return [ObjectKind.PULL_REQUEST]

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
            if not payload.get("pull_request") or not payload.get("repository"):
                logger.warning("Missing required fields in pull request webhook payload")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating pull request webhook payload: {e}")
            return False
