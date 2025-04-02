from typing import List, Optional, Dict, Any
from loguru import logger
from github_cloud.helpers.utils import ObjectKind
from github_cloud.helpers.constants import REPO_DELETE_EVENTS, REPO_UPSERT_EVENTS
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
from github_cloud.webhook_processors.events import RepositoryEvent

class RepositoryEventPipeline(BaseEventPipeline[RepositoryEvent]):
    """Pipeline for processing GitHub repository events."""
    
    def __init__(self):
        super().__init__()
        self.client = init_client()

    def _extract_event_data(self, payload: EventPayload) -> Optional[RepositoryEvent]:
        """Extract and validate event data from the payload."""
        try:
            action = payload.get("action")
            repo = payload.get("repository", {})
            org = payload.get("organization", {})
            
            if not self._validate_required_fields(repo, ["name"]) or not org:
                logger.warning("Missing required data in payload")
                return None
                
            return RepositoryEvent(
                action=action,
                repo_name=repo.get("name"),
                org_name=org.get("login"),
                repo_data=repo,
                organization_data=org
            )
        except Exception as e:
            logger.error(f"Failed to extract event data: {e}")
            return None

    async def _handle_delete(self, event: RepositoryEvent) -> WebhookEventRawResults:
        """Handle repository deletion events."""
        logger.info(f"Repository {event.repo_name} was deleted in {event.org_name}")
        return WebhookEventRawResults(
            modified_resources=[],
            removed_resources=[event.repo_data],
        )

    async def _handle_upsert(self, event: RepositoryEvent) -> WebhookEventRawResults:
        """Handle repository creation/update events."""
        try:
            latest_repo = await self.client.fetch_resource(
                ObjectKind.REPOSITORY,
                f"{event.org_name}/{event.repo_name}"
            )
            
            if not latest_repo:
                logger.warning(f"Unable to retrieve modified resource data for repository {event.org_name}/{event.repo_name}")
                return WebhookEventRawResults(
                    modified_resources=[],
                    removed_resources=[],
                )
                
            logger.info(f"Successfully retrieved modified resource data for repository {event.org_name}/{event.repo_name}")
            return WebhookEventRawResults(
                modified_resources=[latest_repo],
                removed_resources=[],
            )
        except Exception as e:
            logger.error(f"Error handling repository upsert: {e}")
            return WebhookEventRawResults(
                modified_resources=[],
                removed_resources=[],
            )

    def _determine_handler(self, event: RepositoryEvent) -> str:
        """Determine which handler to use based on the event type."""
        if event.action in REPO_DELETE_EVENTS:
            return 'delete'
        elif event.action in REPO_UPSERT_EVENTS:
            return 'upsert'
        return 'default'

class RepositoryWebhookProcessor(AbstractWebhookProcessor):
    """Main webhook processor for GitHub repositories."""
    
    def __init__(self):
        super().__init__()
        self.pipeline = RepositoryEventPipeline()

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event."""
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")
        return (
            event_name == "repository"
            and event_type in REPO_UPSERT_EVENTS + REPO_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        """Get the resource kinds this processor handles."""
        return [ObjectKind.REPOSITORY]

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
            if not payload.get("repository") or not payload.get("organization"):
                logger.warning("Missing required fields in repository webhook payload")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating repository webhook payload: {e}")
            return False
