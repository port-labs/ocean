from loguru import logger
from harbor.client.client_initializer import get_harbor_client
from harbor.constants import ObjectKind
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


class ProjectWebhookProcessor(AbstractWebhookProcessor):

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """
        Check if event affects projects.
        QUOTA_EXCEED and QUOTA_WARNING events contain project information.
        """
        event_type = event.payload.get("type", "")
        # These events contain project information
        return event_type in ["QUOTA_EXCEED", "QUOTA_WARNING"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECT]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """
        Validate webhook authentication.
        Harbor can be configured with authentication headers in the webhook policy.
        Check the 'Authorization' header or custom auth headers you configured.
        """
        # TODO: Implement based on your Harbor webhook policy authentication setup
        # Example: Check for a shared secret or JWT token
        # auth_header = headers.get("Authorization")
        # return verify_harbor_webhook_signature(auth_header, payload)
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate payload has required Harbor webhook structure"""
        return "type" in payload and "event_data" in payload

    async def handle_event(
        self,
        payload: EventPayload,
        resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Process events that affect projects (quota events).
        Since project modifications aren't directly webhooks, we fetch the project
        to ensure we have the latest state.
        """
        client = get_harbor_client()
        event_type = payload.get("type", "")
        event_data = payload.get("event_data", {})

        # Extract project name from the event
        # Harbor webhook payload structure: event_data.repository.namespace
        repository = event_data.get("repository", {})
        project_name = repository.get(
            "namespace") or repository.get("name", "").split("/")[0]

        if not project_name:
            logger.warning(
                "Could not extract project name from webhook payload")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        logger.info(
            f"Processing project-related event: {event_type} for project: {project_name}")

        # Fetch latest project data
        try:
            project = await client.get_project(project_name)
            if project:
                logger.info(
                    f"Successfully fetched updated project: {project_name}")
                return WebhookEventRawResults(
                    updated_raw_results=[project],
                    deleted_raw_results=[]
                )
        except Exception as e:
            logger.error(f"Failed to fetch project {project_name}: {e}")

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
