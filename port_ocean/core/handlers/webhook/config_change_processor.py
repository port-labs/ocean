from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
    WebhookProcessorType,
)


class BaseConfigChangeWebhookProcessor(AbstractWebhookProcessor):
    """
    Base webhook processor for reacting to configuration changes.

    Processors inheriting from this class are:
    - Marked as ACTION processors, so they are not tied to any specific kind in
      the Port app config mapping.
    - Expected to implement `trigger_resync`, which encapsulates how a full
      resync should be triggered for the integration.
    """

    @classmethod
    def get_processor_type(cls) -> WebhookProcessorType:
        return WebhookProcessorType.ACTION

    async def trigger_resync(self) -> None:
        """Trigger a full resync for the integration."""
        await ocean.sync_raw_all()
