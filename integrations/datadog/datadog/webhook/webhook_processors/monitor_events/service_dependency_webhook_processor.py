import asyncio
from typing import Any, cast

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.client import DatadogClient
from datadog.core.exporters import ServiceDependencyExporter
from datadog.core.exporters.service_dependency_exporter import (
    GetServiceDependencyOptions,
)
from datadog.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)
from datadog.webhook.consts import SERVICE_RELATED_EVENTS


class ServiceDependencyWebhookProcessor(BaseWebhookProcessor):
    @staticmethod
    def extract_service_ids(payload: EventPayload) -> list[str]:
        tags = payload.get("tags")
        if not isinstance(tags, list):
            return []

        service_ids: list[str] = []
        for tag in tags:
            if not isinstance(tag, str) or not tag.startswith("service:"):
                continue
            _, _, service_id = tag.partition(":")
            if service_id:
                service_ids.append(service_id)
        return service_ids

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("event_type", None)
        return (
            event_type in SERVICE_RELATED_EVENTS
            and len(self.extract_service_ids(event.payload)) > 0
        )

    async def get_matching_kinds(self, _: WebhookEvent) -> list[str]:
        return [ObjectKind.SERVICE_DEPENDENCY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        from datadog.overrides import ServiceDependencyResourceConfig

        service_ids = self.extract_service_ids(payload)
        options = [
            GetServiceDependencyOptions.from_resource_config(
                cast(ServiceDependencyResourceConfig, resource_config),
                resource_id=service_id,
            )
            for service_id in service_ids
        ]

        async def fetch(client: DatadogClient) -> list[dict[str, Any]]:
            dep_exporter = ServiceDependencyExporter(client)
            results = await asyncio.gather(
                *(dep_exporter.get_resource(opt) for opt in options)
            )
            return [result for result in results if result]

        org_name = payload.get("org_name")
        clients = self._client_manager.get_clients_by_org_name(org_name)
        service_dependencies = await self._fetch_from_clients(
            clients, fetch, context=f"org '{org_name}'"
        )

        return WebhookEventRawResults(
            updated_raw_results=service_dependencies or [],
            deleted_raw_results=[],
        )
