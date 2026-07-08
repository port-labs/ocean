from typing import cast

from azure.core.exceptions import ResourceNotFoundError
from azure_integration.overrides import (
    AzureCloudResourceSelector,
    AzureSpecificKindSelector,
)
from azure_integration.utils import resource_client_context
from azure_integration.webhook_processors._azure_abstract_webhook_processor import (
    AzureAbstractWebhookProcessor,
    AzureResourceEvent,
)
from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class AzureResourceEventProcessor(AzureAbstractWebhookProcessor):

    async def should_process_event(self, event: WebhookEvent) -> bool:
        self._resource_event: AzureResourceEvent | None = self._parse_resource_event(
            event.payload
        )
        if not self._resource_event:
            return False

        matching_resource_configs = self._get_matching_resource_configs(
            self._resource_event.resource_type
        )
        if not matching_resource_configs:
            logger.info(
                "Resource type not found in port app config, update port app config to include the resource type",
                resource_type=self._resource_event.resource_type,
            )
            return False
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        resource_event = cast(AzureResourceEvent, self._resource_event)
        matching_resource_configs = self._get_matching_resource_configs(
            resource_event.resource_type
        )
        return [config.kind for config in matching_resource_configs]

    async def validate_payload(self, payload: EventPayload) -> bool:
        return self._resource_event is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        resource_event = cast(AzureResourceEvent, self._resource_event)
        logger.info(
            "Received Azure resource event",
            event_id=resource_event.id,
            event_type=resource_event.type,
            resource_provider=resource_event.resource_provider,
            operation_name=resource_event.operation_name,
            subscription_id=resource_event.subscription_id,
        )

        selector = resource_config.selector
        if isinstance(selector, AzureSpecificKindSelector):
            api_version = selector.api_version
        else:
            api_version = cast(AzureCloudResourceSelector, selector).resource_kinds[
                resource_event.resource_type
            ]

        blueprint = resource_config.port.entity.mappings.blueprint.strip('"')

        async with resource_client_context(resource_event.subscription_id) as client:
            try:
                resource = await client.resources.get_by_id(
                    resource_id=resource_event.resource_uri,
                    api_version=api_version,
                )
                return WebhookEventRawResults(
                    updated_raw_results=[dict(resource.as_dict())],
                    deleted_raw_results=[],
                )
            except ResourceNotFoundError:
                logger.info(
                    "Resource not found in azure, unregistering from port",
                    id=resource_event.resource_uri,
                    kind=resource_config.kind,
                    api_version=api_version,
                    blueprint=blueprint,
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"id": resource_event.resource_uri}],
                )
