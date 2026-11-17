from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)

WEBHOOK_PATH = "/webhook"


class AbstractFoundryWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # Foundry returns a platform signing_secret per account webhook (no custom
        # secret). Multi-account → multi-secret with no clean user config. Trust is
        # correlation: handlers only act on response ids bound to in-progress runs.
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return isinstance(payload.get("type"), str) and bool(payload.get("id"))

    @staticmethod
    def get_event_type(payload: EventPayload) -> str:
        event_type = payload.get("type")
        return str(event_type) if event_type else ""
