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
    resolve_resource_type_from_resource_uri,
)
from cloudevents.pydantic import CloudEvent
from loguru import logger
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


class AzureAbstractWebhookProcessor(AbstractWebhookProcessor):

    _resource_event: AzureResourceEvent | None = None

    def _parse_resource_event(self, payload: EventPayload) -> AzureResourceEvent | None:
        try:
            cloud_event = CloudEvent(**payload)

            if not isinstance(cloud_event.data, dict):
                return None

            resource_uri = cloud_event.data["resourceUri"]
            resource_type = resolve_resource_type_from_resource_uri(
                resource_uri=resource_uri
            )

            if not resource_type:
                logger.warning(
                    "Could not resolve resource type from cloud event",
                    resource_uri=resource_uri,
                )
                return None

            return AzureResourceEvent(
                id=cloud_event.id,
                type=cloud_event.type,
                resource_uri=resource_uri,
                operation_name=cloud_event.data["operationName"],
                subscription_id=cloud_event.data["subscriptionId"],
                resource_type=resource_type,
                resource_provider=cloud_event.data.get("resourceProvider"),
            )

        except (KeyError, TypeError, ValueError) as e:
            logger.warning(
                "Failed to parse Azure resource event",
                error=str(e),
                payload=payload,
            )
            return None

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
