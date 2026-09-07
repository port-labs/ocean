from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from clients.pagerduty import PagerDutyClient

MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE = 20


class AbstractPagerDutyExecutor(AbstractExecutor):
    """Base executor for PagerDuty actions."""

    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = PagerDutyClient.from_ocean_configuration()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        info = self.client.get_rate_limit_status()
        if not info:
            return False

        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        info = self.client.get_rate_limit_status()
        if not info:
            return 0.0

        return float(info.seconds_until_reset)
