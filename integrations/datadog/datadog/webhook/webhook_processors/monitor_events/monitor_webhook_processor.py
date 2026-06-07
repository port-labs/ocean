from integration import ObjectKind
from typing import cast
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.core.exporters import MonitorExporter
from datadog.core.exporters.monitor_exporter import GetMonitorOptions
from datadog.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)


class MonitorWebhookProcessor(BaseWebhookProcessor):
    @staticmethod
    def extract_monitor_id(payload: EventPayload) -> str | None:
        alert_id = payload.get("alert_id")
        if alert_id is None:
            return None
        return str(alert_id)

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.payload.get("event_type") is not None
            and self.extract_monitor_id(event.payload) is not None
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MONITOR]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        from datadog.overrides import MonitorResourceConfig

        monitor_id = self.extract_monitor_id(payload)
        if monitor_id is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        monitor = await MonitorExporter(self.client).get_resource(
            GetMonitorOptions.from_resource_config(
                cast(MonitorResourceConfig, resource_config), id=monitor_id
            )
        )

        return WebhookEventRawResults(
            updated_raw_results=[monitor] if monitor else [],
            deleted_raw_results=[],
        )
