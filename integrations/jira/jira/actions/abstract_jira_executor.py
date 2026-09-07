from abc import ABC

from initialize_client import get_or_create_jira_client
from jira.client import JiraClient
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun


class AbstractJiraExecutor(AbstractExecutor, ABC):
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self._client: JiraClient | None = None

    @property
    def client(self) -> JiraClient:
        if self._client is None:
            self._client = get_or_create_jira_client()
        return self._client

    @client.setter
    def client(self, value: JiraClient) -> None:
        self._client = value

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return False

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return 0.0
