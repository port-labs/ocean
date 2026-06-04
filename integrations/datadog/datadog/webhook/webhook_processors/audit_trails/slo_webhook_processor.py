import httpx
from typing import Any, cast

from integration import ObjectKind
from datadog.overrides import SLOResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.core.exporters import SloExporter
from datadog.core.exporters.slo_exporter import GetSloOptions
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


class SloWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.SLO]

    def _matches(self, event: dict[str, Any]) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#service-level-objectives
        return (
            self.extract_evt_name(event) == "SLO"
            and self.extract_asset_type(event) == ObjectKind.SLO
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return isinstance(event.payload, dict) and self._matches(event.payload)

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        slo_id = self.extract_asset_id(payload)
        if not slo_id:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if self.is_delete_event(payload):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": slo_id}]
            )

        config = cast(SLOResourceConfig, resource_config)
        try:
            slo = await SloExporter(self.client).get_resource(
                GetSloOptions(
                    id=slo_id,
                    include_restriction_policy=config.selector.include_restriction_policy,
                )
            )
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[{"id": slo_id}]
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[slo] if slo else [], deleted_raw_results=[]
        )
