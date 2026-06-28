from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)

from clients.client_factory import create_anthropic_client


class AbstractAnthropicWebhookProcessor(AbstractWebhookProcessor):
    """Base webhook processor for Claude Managed Agents events.

    Anthropic webhooks follow the Standard Webhooks spec. The event type and the
    triggering resource id live under `payload["data"]`.
    """

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        client = create_anthropic_client()
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
        return data.get("id", "")
