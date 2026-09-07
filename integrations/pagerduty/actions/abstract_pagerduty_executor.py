from clients.rate_limiter import RateLimitInfo
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

    @staticmethod
    def _is_snapshot_close_to_rate_limit(info: RateLimitInfo | None) -> bool:
        """Treat an expired snapshot as replenished.

        The execution manager backs off without making PagerDuty requests, so
        `remaining` never refreshes on its own. Once the reset window has
        passed we must allow the run to proceed even if the cached remaining
        count is still low.
        """
        if info is None or info.limit == 0 or info.seconds_until_reset <= 0:
            return False

        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return self._is_snapshot_close_to_rate_limit(
            self.client.get_rate_limit_status()
        )

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        info = self.client.get_rate_limit_status()
        if info is None or not self._is_snapshot_close_to_rate_limit(info):
            return 0.0

        return float(info.seconds_until_reset)
