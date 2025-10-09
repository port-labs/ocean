from typing import Any, Iterable

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
)


class OktaBaseWebhookProcessor(AbstractWebhookProcessor):
    def _has_allowed_event(
        self,
        payload: EventPayload,
        allowed_event_types: Iterable[str],
        target_type: str,
    ) -> bool:
        events = payload.get("data", {}).get("events")
        if not isinstance(events, list) or not events:
            return False
        allowed = set(allowed_event_types)
        for event_object in events:
            event_type = event_object.get("eventType")
            if not isinstance(event_type, str) or event_type not in allowed:
                continue
            for target in event_object.get("target", []):
                if target.get("type") == target_type and target.get("id"):
                    return True
        return False

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Authenticate webhook using optional Authorization header if provided.

        Okta Event Hooks support an authScheme that forwards a static header (e.g., Authorization)
        with each call. If a webhook_secret is configured, we expect the Authorization header
        to match it exactly. If no secret configured, accept events.
        """
        if event._original_request is None:
            return False

        webhook_secret = ocean.integration_config.get("webhook_secret")
        if not webhook_secret:
            logger.info(
                "No secret configured for Okta incoming webhooks; accepting event without signature validation."
            )
            return True

        provided = event.headers.get("authorization", "")
        return provided == webhook_secret

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Basic validation: ensure payload has data.events list."""
        return isinstance(payload, dict) and isinstance(
            payload.get("data", {}).get("events"), list
        )
