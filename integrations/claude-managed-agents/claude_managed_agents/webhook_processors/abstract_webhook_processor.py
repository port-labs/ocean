from typing import Any

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEventRawResults,
)

from claude_managed_agents.clients.client_factory import create_webhook_client
from claude_managed_agents.integration import ArchivableSelector


class AbstractAnthropicWebhookProcessor(AbstractWebhookProcessor):
    """Base webhook processor for Claude Managed Agents events.

    Anthropic webhooks follow the Standard Webhooks spec. The event type and the
    triggering resource id live under `payload["data"]`.
    """

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        client = create_webhook_client()
        if not client.verify_webhook_secrets:
            return True

        if not client.has_webhook_secret:
            logger.warning(
                "Skipping webhook signature verification because no signing secret is configured"
            )
            return True

        request = self.event._original_request
        if request is None:
            logger.error("Cannot verify webhook signature without the original request")
            return False

        try:
            raw_body = (await request.body()).decode("utf-8")
            client.unwrap_webhook(raw_body, headers)
            return True
        except Exception as error:
            logger.error(f"Webhook signature verification failed: {error}")
            return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        data = payload.get("data")
        return bool(isinstance(data, dict) and data.get("type") and data.get("id"))

    @staticmethod
    def get_event_type(payload: EventPayload) -> str:
        data = payload.get("data") or {}
        return data.get("type", "")

    @staticmethod
    def get_resource_id(payload: EventPayload) -> str:
        data = payload.get("data") or {}
        return str(data.get("id") or "")

    def build_upsert_results(
        self,
        raw: dict[str, Any],
        resource_config: ResourceConfig | None,
        event_type: str,
    ) -> WebhookEventRawResults:
        """Upsert `raw`, or delete it when it is archived and the resource's
        `includeArchived` selector is off, matching what a resync would keep."""
        resource_id = raw["id"]
        resource_name = event_type.split(".")[0]

        selector = resource_config.selector if resource_config else None
        include_archived = (
            not isinstance(selector, ArchivableSelector) or selector.include_archived
        )

        if raw.get("archived_at") and not include_archived:
            logger.info(
                f"Deleting archived {resource_name} {resource_id} from catalog "
                f"because includeArchived is disabled ({event_type})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": resource_id}]
            )

        logger.info(f"Upserting {resource_name} {resource_id} ({event_type})")
        return WebhookEventRawResults(updated_raw_results=[raw], deleted_raw_results=[])
