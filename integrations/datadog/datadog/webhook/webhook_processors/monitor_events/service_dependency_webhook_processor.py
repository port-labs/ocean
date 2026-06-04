import asyncio
from typing import Any, Union, cast

from loguru import logger

from initialize_client import init_client
from integration import ObjectKind
from datadog.overrides import DatadogServiceDependencySelector, ServiceDependencyResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.core.exporters import ServiceDependencyExporter
from datadog.core.exporters.service_dependency_exporter import (
    GetServiceDependencyOptions,
)
from datadog.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)


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
        event_type = event.payload["event_type"]
        service_related_events = [
            "service_check",
            "query_alert_monitor",
            "metric_slo_alert",
            "monitor_slo_alert",
            "outlier_monitor",
            "event_v2_alert",
        ]
        return event_type in service_related_events

    async def get_matching_kinds(self, _: WebhookEvent) -> list[str]:
        return [ObjectKind.SERVICE_DEPENDENCY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        service_ids = self.extract_service_ids(payload)
        config = cast(
            Union[ResourceConfig, ServiceDependencyResourceConfig], resource_config
        )
        selector = cast(DatadogServiceDependencySelector, config.selector)

        dd_client = init_client()
        dep_exporter = ServiceDependencyExporter(dd_client)
        tasks = [
            dep_exporter.get_resource(
                GetServiceDependencyOptions(
                    service_id=service_id,
                    env=selector.environment,
                    start_time=selector.start_time,
                )
            )
            for service_id in service_ids
        ]
        results: list[dict[str, Any] | None] = await asyncio.gather(*tasks)
        service_dependencies = [result for result in results if result]

        return WebhookEventRawResults(
            updated_raw_results=service_dependencies,
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        has_event_info = "event_type" in payload
        service_tags = self.extract_service_ids(payload)
        has_service_info = bool(service_tags and all(service_tags))

        is_valid = has_service_info and has_event_info
        if not is_valid:
            logger.warning(f"Invalid webhook payload for service dependency: {payload}")

        return is_valid
