from abc import ABC, abstractmethod
from typing import Any
from azure_devops.webhooks.webhook_event import WebhookEvent
from azure_devops.client.azure_devops_client import AzureDevopsClient


class HookListener(ABC):
    webhook_events: list[WebhookEvent]

    def __init__(self, azure_devops_client: AzureDevopsClient) -> None:
        self._client = azure_devops_client

    @abstractmethod
    async def on_hook(self, data: dict[str, Any]) -> None:
        pass
