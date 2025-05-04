
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)


class _LaunchDarklyAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for LaunchDarkly webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains all required fields."""
        return not ({"kind", "_links", "accesses"} - payload.keys())

    def is_deletion_event(self, payload: EventPayload) -> bool:
        """
        Returns True if the event is a deletion or archive event based on the payload's titleVerb.

        Args:
            title_verb: The titleVerb string from the payload.
        """
        return any(word in payload["titleVerb"] for word in ["deleted", "archived"])
