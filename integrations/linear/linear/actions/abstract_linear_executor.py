from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from linear.client import LinearClient

MIN_REMAINING_REQUESTS_FOR_EXECUTE = 20
MIN_REMAINING_COMPLEXITY_FOR_EXECUTE = 5_000


class AbstractLinearExecutor(AbstractExecutor):
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = LinearClient.create_from_ocean_configuration()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        rate_limit_status = self.client.get_rate_limit_status()
        if rate_limit_status is None:
            return False
        if (
            rate_limit_status.requests_remaining is not None
            and rate_limit_status.requests_remaining < MIN_REMAINING_REQUESTS_FOR_EXECUTE
        ):
            return True
        if (
            rate_limit_status.complexity_remaining is not None
            and rate_limit_status.complexity_remaining
            < MIN_REMAINING_COMPLEXITY_FOR_EXECUTE
        ):
            return True
        return False

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        rate_limit_status = self.client.get_rate_limit_status()
        if rate_limit_status is None:
            return 0.0
        return rate_limit_status.seconds_until_reset()
