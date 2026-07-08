from abc import abstractmethod
from dataclasses import dataclass

from azure_integration.overrides import (
    AzureCustomKindResourceConfig,
    AzureCloudResourceConfig,
    AzureResourceGroupResourceConfig,
    AzureSubscriptionResourceConfig,
    AzurePortAppConfig,
)
from azure_integration.utils import (
    get_resource_configs_with_resource_kind,
)
from port_ocean.context.event import event as port_event
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from typing import cast


@dataclass(frozen=True)
class AzureResourceEvent:
    id: str
    type: str
    resource_uri: str
    operation_name: str
    subscription_id: str
    resource_type: str
    resource_provider: str | None


class BaseWebhookProcessor(AbstractWebhookProcessor):

    def _get_matching_resource_configs(
        self, resource_type: str
    ) -> list[
        AzureResourceGroupResourceConfig
        | AzureSubscriptionResourceConfig
        | AzureCloudResourceConfig
        | AzureCustomKindResourceConfig
    ]:
        return get_resource_configs_with_resource_kind(
            resource_kind=resource_type,
            resource_configs=cast(
                AzurePortAppConfig, port_event.port_app_config
            ).resources,
        )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    @abstractmethod
    async def should_process_event(self, event: WebhookEvent) -> bool: ...
