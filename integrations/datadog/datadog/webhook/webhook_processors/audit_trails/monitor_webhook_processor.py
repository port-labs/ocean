import httpx

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
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseProcessor,
)


class MonitorWebhookProcessor(BaseProcessor):
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
        return (
            await super().should_process_event(event)
            and self.extract_asset_type(event.payload) == ObjectKind.MONITOR
        )

    async def get_matching_kinds(self, _: WebhookEvent) -> list[str]:
        return [ObjectKind.MONITOR]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        monitor_id = self.extract_asset_id(payload)
        if monitor_id is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if self.is_delete_event(payload):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": monitor_id}],
            )

        dd_client = init_client()
        monitor_exporter = MonitorExporter(dd_client)
        try:
            monitor = await monitor_exporter.get_resource(
                GetMonitorOptions(
                    resource_id=monitor_id,
                    include_restriction_policy=self._should_include_restriction_policy(
                        resource_config
                    ),
                )
            )
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"id": monitor_id}],
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[monitor] if monitor else [],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        return self.extract_asset_id(payload) is not None
