from typing import cast, Union, Any

from initialize_client import init_client
from integration import ObjectKind
from overrides import ServiceDependencyResourceConfig, DatadogServiceDependencySelector
from webhook_processors._abstract_webhook_processor import (
    _AbstractDatadogWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from loguru import logger
import asyncio


class ServiceDependencyWebhookProcessor(_AbstractDatadogWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Only process events that are related to service dependencies."""
        event_type = event.payload["event_type"]

        # Event types that may indicate changes in service behavior or dependencies
        service_related_events = [
            "service_check",
            "query_alert_monitor",
            "metric_slo_alert",
            "monitor_slo_alert",
            "outlier_monitor",
            "event_v2_alert",
        ]

        should_process = event_type in service_related_events
        return should_process

    async def get_matching_kinds(self, _: WebhookEvent) -> list[str]:
        return [ObjectKind.SERVICE_DEPENDENCY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        service_ids: list[str] = []
        for tag in payload["tags"]:
            if tag.startswith("service:"):
                service_ids.append(tag.split(":")[1])

        config = cast(
            Union[ResourceConfig, ServiceDependencyResourceConfig], resource_config
        )
        selector = cast(DatadogServiceDependencySelector, config.selector)
        dd_client = init_client()

        tasks = [
            dd_client.get_single_service_dependency(
                service_id=service_id,
                env=selector.environment,
                start_time=selector.start_time,
            )
            for service_id in service_ids
        ]

        results: list[dict[str, Any] | None] = await asyncio.gather(*tasks)
        service_dependencies = [
            service_dependency for service_dependency in results if service_dependency
        ]

        return WebhookEventRawResults(
            updated_raw_results=service_dependencies,
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        has_event_info = "event_type" in payload

        has_service_info = False
        if "tags" in payload:
            service_tags = [tag for tag in payload["tags"] if tag.startswith("service:")]
            if service_tags:
                if all(len(tag.split(":", 1)) > 1 and tag.split(":", 1)[1] for tag in service_tags):
                    has_service_info = True

        is_valid = has_service_info and has_event_info
        if not is_valid:
            logger.warning(f"Invalid webhook payload for service dependency: {payload}")

        return is_valid
