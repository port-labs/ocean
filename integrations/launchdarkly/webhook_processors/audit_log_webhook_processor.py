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


class AuditLogWebhookProcessor(_LaunchDarklyAbstractWebhookProcessor):
    """Processes audit log events from LaunchDarkly."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event header contains required AuditLog event type."""
        return event.payload.get("kind") == ObjectKind.AUDITLOG

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.AUDITLOG]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the audit log event and return the raw results."""
        endpoint = payload["_links"]["canonical"]["href"]

        logger.info(f"Processing webhook event for audit log from endpoint: {endpoint}")

        client = LaunchDarklyClient.create_from_ocean_configuration()
        data_to_update = await client.send_api_request(endpoint)

        # Audit logs are immutable, so we only handle creation events
        return WebhookEventRawResults(
            updated_raw_results=[data_to_update], deleted_raw_results=[]
        )
