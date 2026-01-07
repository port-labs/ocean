"""Webhook processor for Harbor artifact events."""

from loguru import logger

from harbor.utils import parse_resource_url
from initialize_client import get_harbor_client
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class ArtifactWebhookProcessor(AbstractWebhookProcessor):
    """
    Webhook processor for Harbor artifact events.
    
    Handles the following Harbor webhook events:
    - PUSH_ARTIFACT: Fetches fresh artifact data and updates Port
    - DELETE_ARTIFACT: Removes artifact from Port
    - PULL_ARTIFACT: Ignored (doesn't change artifact data)
    
    This processor:
    1. Authenticates incoming webhook requests
    2. Validates the payload structure
    3. Fetches fresh data from Harbor API for push events
    4. Returns appropriate results for Port to process
    """

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """
        Determine if this processor should handle the event.
        
        Only processes PUSH_ARTIFACT and DELETE_ARTIFACT events.
        PULL_ARTIFACT events are ignored as they don't change artifact data.
        
        Args:
            event: The webhook event
        
        Returns:
            True if the event should be processed, False otherwise
        """
        event_type = event.payload.get("type", "")
        
        # Ignore PULL_ARTIFACT events as they don't change artifact data
        if event_type == "PULL_ARTIFACT":
            logger.debug("Ignoring PULL_ARTIFACT event - no data changes")
            return False
        
        # Process PUSH and DELETE events
        return event_type in ["PUSH_ARTIFACT", "DELETE_ARTIFACT"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """
        Return the resource kinds this event affects.
        
        Args:
            event: The webhook event
        
        Returns:
            List of resource kind strings
        """
        return ["artifacts"]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """
        Authenticate the webhook request.
        
        Compares the authorization header with the configured webhook secret.
        If no webhook secret is configured, authentication is skipped.
        
        Args:
            payload: The webhook payload
            headers: The webhook headers
        
        Returns:
            True if authentication succeeds, False otherwise
        """
        webhook_secret = ocean.integration_config.get("webhook_secret")
        
        if not webhook_secret:
            logger.warning("No webhook_secret configured, skipping authentication")
            return True
        
        # Get authorization header (case-insensitive lookup)
        auth_header = headers.get("authorization") or headers.get("Authorization")
        
        if not auth_header:
            logger.error("No authorization header found in webhook request")
            return False
        
        # Direct string comparison (plain match, no encryption)
        is_valid = auth_header == webhook_secret
        
        if not is_valid:
            logger.error("Webhook authentication failed: invalid authorization header")
        
        return is_valid

    async def validate_payload(self, payload: EventPayload) -> bool:
        """
        Validate that the webhook payload has the required structure.
        
        Checks for:
        - Required top-level fields: 'type', 'event_data'
        - Required fields in event_data: 'resources', 'repository'
        - Resources must be a non-empty list
        - First resource must have 'digest' and 'resource_url'
        
        Args:
            payload: The webhook payload
        
        Returns:
            True if payload is valid, False otherwise
        """
        # Check required top-level fields
        if not payload.get("type"):
            logger.error("Missing 'type' field in webhook payload")
            return False
        
        if not payload.get("event_data"):
            logger.error("Missing 'event_data' field in webhook payload")
            return False
        
        event_data = payload["event_data"]
        
        # Check required fields in event_data
        if not event_data.get("resources"):
            logger.error("Missing 'resources' field in event_data")
            return False
        
        if not event_data.get("repository"):
            logger.error("Missing 'repository' field in event_data")
            return False
        
        # Check that resources is a non-empty list
        resources = event_data["resources"]
        if not isinstance(resources, list) or len(resources) == 0:
            logger.error("'resources' must be a non-empty list")
            return False
        
        # Check required fields in the first resource
        resource = resources[0]
        if not resource.get("digest"):
            logger.error("Missing 'digest' field in resource")
            return False
        
        if not resource.get("resource_url"):
            logger.error("Missing 'resource_url' field in resource")
            return False
        
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Process the webhook event and return results.
        
        For PUSH_ARTIFACT events:
        - Parses the resource URL to extract project/repo/reference
        - Fetches fresh artifact data from Harbor API
        - Returns the artifact for Port to update
        
        For DELETE_ARTIFACT events:
        - Returns the artifact digest for Port to delete
        
        Args:
            payload: The webhook payload
            resource_config: The resource configuration from Port
        
        Returns:
            WebhookEventRawResults with updated or deleted artifacts
        """
        event_type = payload["type"]
        event_data = payload["event_data"]
        resource = event_data["resources"][0]  # Get first resource
        
        digest = resource["digest"]
        resource_url = resource["resource_url"]
        
        logger.info(f"Processing {event_type} event for artifact: {digest}")
        
        # Parse the resource URL to get project, repo, and reference
        try:
            project_name, repository_name, reference = parse_resource_url(resource_url)
        except Exception as e:
            logger.error(f"Failed to parse resource URL, skipping event: {str(e)}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )
        
        if event_type == "DELETE_ARTIFACT":
            return self._handle_delete_event(digest)
        elif event_type == "PUSH_ARTIFACT":
            return await self._handle_push_event(
                digest, project_name, repository_name, reference
            )
        
        # Should not reach here due to should_process_event() filter
        logger.warning(f"Unexpected event type: {event_type}")
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )

    @staticmethod
    def _handle_delete_event(digest: str) -> WebhookEventRawResults:
        """
        Handle DELETE_ARTIFACT event.
        
        Args:
            digest: The artifact digest
        
        Returns:
            WebhookEventRawResults with the deleted artifact
        """
        logger.info(f"Artifact {digest} was deleted")
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[{"digest": digest}],
        )

    @staticmethod
    async def _handle_push_event(
        digest: str,
        project_name: str,
        repository_name: str,
        reference: str,
    ) -> WebhookEventRawResults:
        """
        Handle PUSH_ARTIFACT event by fetching fresh data from Harbor API.
        
        Args:
            digest: The artifact digest
            project_name: The project name
            repository_name: The repository name
            reference: The artifact reference (tag or digest)
        
        Returns:
            WebhookEventRawResults with the updated artifact
        """
        client = get_harbor_client()
        
        logger.info(
            f"Fetching fresh artifact data for {project_name}/{repository_name} "
            f"with digest {digest}"
        )
        
        try:
            # Use digest as reference for most reliable fetch
            artifact = await client.get_single_artifact(
                project_name=project_name,
                repository_name=repository_name,
                reference=digest,
            )
            
            if not artifact:
                logger.warning(
                    f"Artifact not found in Harbor API: "
                    f"{project_name}/{repository_name}/{digest}"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )
            
            logger.info(f"Successfully fetched artifact data for {digest}")
            return WebhookEventRawResults(
                updated_raw_results=[artifact],
                deleted_raw_results=[],
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch artifact from Harbor API: {str(e)}")
            # Don't fail the webhook, just return empty results
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )
