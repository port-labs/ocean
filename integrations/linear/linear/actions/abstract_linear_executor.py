from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from linear.client import LinearClient


class AbstractLinearExecutor(AbstractExecutor):
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = LinearClient.create_from_ocean_configuration()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        rate_limit_status = self.client.get_rate_limit_status()
        if rate_limit_status is None:
            return False
        return rate_limit_status.is_close_to_limit()

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        rate_limit_status = self.client.get_rate_limit_status()
        if rate_limit_status is None:
            return 0.0
        return rate_limit_status.seconds_until_reset()
