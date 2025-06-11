from webhook_processors.launchdarkly_abstract_webhook_processor import (
    _LaunchDarklyAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from client import LaunchDarklyClient, ObjectKind
from loguru import logger
from webhook_processors.utils import (
    extract_project_key_from_endpoint,
    enrich_resource_with_project,
)


class EnvironmentWebhookProcessor(_LaunchDarklyAbstractWebhookProcessor):
    """Processes environment-related webhook events from LaunchDarkly."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event header contains required Environment event type."""
        return event.payload.get("kind") == ObjectKind.ENVIRONMENT

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ENVIRONMENT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the environment webhook event and return the raw results."""
        endpoint = payload["_links"]["canonical"]["href"]
        kind = payload["kind"]

        logger.info(
            f"Processing webhook event for environment from endpoint: {endpoint}"
        )

        project_key = extract_project_key_from_endpoint(endpoint, kind)
        environment_key = endpoint.strip("/").split("/")[-1]
        environment = {"key": environment_key, "__projectKey": project_key, **payload}

        if self.is_deletion_event(payload):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[environment]
            )

        client = LaunchDarklyClient.create_from_ocean_configuration()
        data_to_update = await enrich_resource_with_project(endpoint, kind, client)

        return WebhookEventRawResults(
            updated_raw_results=[data_to_update], deleted_raw_results=[]
        )
