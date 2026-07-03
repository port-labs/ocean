from dataclasses import dataclass

from azure_integration.overrides import (
    AzureCloudResourceSelector,
    AzureSpecificKindSelector,
)
from cloudevents.pydantic import CloudEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from loguru import logger
from azure.core.exceptions import ResourceNotFoundError
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEventRawResults,
    WebhookEvent,
)
from port_ocean.context.event import event as port_event
from azure_integration.overrides import AzurePortAppConfig
from azure_integration.utils import get_resource_configs_with_resource_kind
from typing import cast

from azure_integration.utils import (
    resolve_resource_type_from_resource_uri,
    resource_client_context,
)


@dataclass(frozen=True)
class AzureResourceEvent:
    id: str
    type: str
    resource_uri: str
    operation_name: str
    subscription_id: str
    resource_type: str
    resource_provider: str | None


class AzureResourceEventProcessor(AbstractWebhookProcessor):
    """
    Handles System events from Azure Event Grid by the Azure subscription resource and registers them in Port
    https://learn.microsoft.com/en-us/azure/event-grid/event-schema-subscriptions?tabs=event-grid-event-schema
    https://learn.microsoft.com/en-us/azure/event-grid/cloud-event-schema
    """

    def _parse_resource_event(self, payload: EventPayload) -> AzureResourceEvent | None:
        try:
            event = CloudEvent(**payload)

            if not isinstance(event.data, dict):
                return None

            resource_uri = event.data["resourceUri"]
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
                id=event.id,
                type=event.type,
                resource_uri=resource_uri,
                operation_name=event.data["operationName"],
                subscription_id=event.data["subscriptionId"],
                resource_type=resource_type,
                resource_provider=event.data.get("resourceProvider"),
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(
                "Failed to parse Azure resource event",
                error=str(e),
                payload=payload,
            )
            return None

    def _api_version(self, resource_config: ResourceConfig, resource_type: str) -> str:
        selector = resource_config.selector
        if isinstance(selector, AzureSpecificKindSelector):
            return selector.api_version
        return cast(AzureCloudResourceSelector, selector).resource_kinds[resource_type]

    def _blueprint(self, resource_config: ResourceConfig) -> str:
        return resource_config.port.entity.mappings.blueprint.strip('"')

    async def should_process_event(self, event: WebhookEvent) -> bool:
        resource_event = self._parse_resource_event(event.payload)

        if not resource_event:
            return False

        matching_resource_configs = get_resource_configs_with_resource_kind(
            resource_kind=resource_event.resource_type,
            resource_configs=cast(
                AzurePortAppConfig, port_event.port_app_config
            ).resources,
        )

        if not matching_resource_configs:
            logger.info(
                "Resource type not found in port app config, update port app config to include the resource type",
                resource_type=resource_event.resource_type,
            )
            return False
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        resource_event = self._parse_resource_event(event.payload)
        return [resource_event.resource_type] if resource_event else []

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return self._parse_resource_event(payload) is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        event = self._parse_resource_event(payload)
        if not event:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        logger.info(
            "Received Azure resource event",
            event_id=event.id,
            event_type=event.type,
            resource_provider=event.resource_provider,
            operation_name=event.operation_name,
            subscription_id=event.subscription_id,
        )

        api_version = self._api_version(resource_config, event.resource_type)
        blueprint = self._blueprint(resource_config)

        async with resource_client_context(event.subscription_id) as client:
            try:
                resource = await client.resources.get_by_id(
                    resource_id=event.resource_uri,
                    api_version=api_version,
                )

                return WebhookEventRawResults(
                    updated_raw_results=[dict(resource.as_dict())],
                    deleted_raw_results=[],
                )
            except ResourceNotFoundError:
                logger.info(
                    "Resource not found in azure, unregistering from port",
                    id=event.resource_uri,
                    kind=resource_config.kind,
                    api_version=api_version,
                    blueprint=blueprint,
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"id": event.resource_uri}],
                )
