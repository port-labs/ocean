from abc import ABC

from initialize_client import get_or_create_jira_client
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun


class AbstractJiraExecutor(AbstractExecutor, ABC):
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = get_or_create_jira_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return False

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return 0.0
