from typing import cast, Union

from initialize_client import init_client
from integration import ObjectKind
from overrides import DatadogResourceConfig, ServiceDependencyResourceConfig
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


class ServiceDependencyWebhookProcessor(_AbstractDatadogWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Only process events that are related to service dependencies."""
        payload = event.payload
        event_type = payload.get("event_type", "")

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
        """Handle service dependency webhook events."""
        selector = cast(Union[ResourceConfig, ServiceDependencyResourceConfig], resource_config).selector
        dd_client = init_client()
        service_dependency = await dd_client.get_single_service_dependency(
            service_id=payload["service_id"],
            env=selector.environment,
            start_time=selector.start_time,
        )

        return WebhookEventRawResults(
            updated_raw_results=[service_dependency] if service_dependency else [],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required fields for service dependency events."""
        has_service_info = "service_id" in payload
        has_event_info = "event_type" in payload

        is_valid = has_service_info and has_event_info

        if not is_valid:
            logger.warning(f"Invalid webhook payload for service dependency: {payload}")

        return is_valid
