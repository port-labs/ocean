from loguru import logger
from initialize_client import create_jira_client
from object_kind import ObjectKind
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


class JiraUserWebhookProcessor(AbstractWebhookProcessor):
    def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("user_")

    def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.USER]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # For Jira webhooks, we don't need additional authentication as they are validated
        # through the webhook secret in the URL
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        # Validate that the payload contains the required fields
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        webhook_event = payload.get("webhookEvent")

        if not webhook_event:
            logger.error("Missing webhook event")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        client = create_jira_client()
        account_id = payload["user"]["accountId"]
        logger.debug(f"Fetching user with accountId: {account_id}")
        item = await client.get_single_user(account_id)

        if not item:
            logger.warning(f"Failed to retrieve {ObjectKind.USER}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        data_to_update = []
        data_to_delete = []
        logger.debug(f"Retrieved {ObjectKind.USER} item: {item}")

        if "deleted" in webhook_event:
            data_to_delete.extend([item])
        else:
            data_to_update.extend([item])

        return WebhookEventRawResults(
            updated_raw_results=data_to_update,
            deleted_raw_results=data_to_delete,
        )
