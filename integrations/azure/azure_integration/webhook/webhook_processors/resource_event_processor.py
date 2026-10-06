from typing import cast

from azure.core.exceptions import ResourceNotFoundError
from azure_integration.overrides import (
    AzureCloudResourceSelector,
    AzureSpecificKindSelector,
)
from azure_integration.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
    AzureResourceEvent,
)
from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_integration.utils import (
    resource_client_context,
    resolve_resource_type_from_resource_uri,
)
from cloudevents.pydantic import CloudEvent


class AzureResourceEventProcessor(BaseWebhookProcessor):
    _cached_resource_event: AzureResourceEvent | None = None

    def _get_parsed_event(self, payload: EventPayload) -> AzureResourceEvent | None:
        if self._cached_resource_event is not None:
            return self._cached_resource_event

        parsed_event = None
        try:
            cloud_event = CloudEvent(**payload)
            if isinstance(cloud_event.data, dict):
                resource_uri = cloud_event.data["resourceUri"]
                resource_type = resolve_resource_type_from_resource_uri(
                    resource_uri=resource_uri
                )
                if resource_type:
                    parsed_event = AzureResourceEvent(
                        id=cloud_event.id,
                        type=cloud_event.type,
                        resource_uri=resource_uri,
                        operation_name=cloud_event.data["operationName"],
                        subscription_id=cloud_event.data["subscriptionId"],
                        resource_type=resource_type,
                        resource_provider=cloud_event.data.get("resourceProvider"),
                    )
                else:
                    logger.warning(
                        "Could not resolve resource type from cloud event",
                        resource_uri=resource_uri,
                    )

        except (KeyError, TypeError, ValueError) as e:
            logger.warning(
                "Failed to parse Azure resource event",
                error=str(e),
                payload=payload,
            )
        self._cached_resource_event = parsed_event
        return parsed_event

    async def should_process_event(self, event: WebhookEvent) -> bool:
        resource_event = self._get_parsed_event(event.payload)
        if not resource_event:
            return False

        matching_resource_configs = self._get_matching_resource_configs(
            resource_event.resource_type
        )
        if not matching_resource_configs:
            logger.info(
                "Resource type not found in port app config, update port app config to include the resource type",
                resource_type=resource_event.resource_type,
            )
            return False
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        resource_event = cast(AzureResourceEvent, self._get_parsed_event(event.payload))
        matching_resource_configs = self._get_matching_resource_configs(
            resource_event.resource_type
        )
        return [config.kind for config in matching_resource_configs]

    async def validate_payload(self, payload: EventPayload) -> bool:
        return self._get_parsed_event(payload) is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        resource_event = cast(AzureResourceEvent, self._get_parsed_event(payload))

        if not resource_event:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

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
