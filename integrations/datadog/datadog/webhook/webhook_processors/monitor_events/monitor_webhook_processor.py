from initialize_client import init_client
from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.core.exporters import MonitorExporter
from datadog.core.exporters.monitor_exporter import GetMonitorOptions
from datadog.webhook.webhook_processors.monitor_events.base_processor import (
    BaseMonitorEventsWebhookProcessor,
)


class MonitorWebhookProcessor(BaseMonitorEventsWebhookProcessor):
    @staticmethod
    def _should_include_restriction_policy(resource_config: ResourceConfig) -> bool:
        if isinstance(resource_config, dict):
            selector = resource_config.get("selector")
            if isinstance(selector, dict):
                return bool(selector.get("include_restriction_policy", False))
            return False

        selector = getattr(resource_config, "selector", None)
        return bool(getattr(selector, "include_restriction_policy", False))

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MONITOR]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        monitor_id = self.extract_monitor_id(payload)
        if monitor_id is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        dd_client = init_client()
        monitor_exporter = MonitorExporter(dd_client)
        monitor = await monitor_exporter.get_resource(
            GetMonitorOptions(
                resource_id=monitor_id,
                include_restriction_policy=self._should_include_restriction_policy(
                    resource_config
                ),
            )
        )

        return WebhookEventRawResults(
            updated_raw_results=[monitor] if monitor else [],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "event_type" in payload and self.extract_monitor_id(payload) is not None
