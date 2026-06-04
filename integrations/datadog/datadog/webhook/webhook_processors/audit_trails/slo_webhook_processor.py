import httpx
from typing import Any, cast

from integration import ObjectKind
from datadog.overrides import SLOResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
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

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not isinstance(event.payload, dict):
            return False
        # https://docs.datadoghq.com/account_management/audit_trail/events/#service-level-objectives
        e = self.parse_event(event.payload)
        return (
            e.attributes.evt.name == "SLO"
            and e.attributes.asset is not None
            and e.attributes.asset.type == ObjectKind.SLO
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        event = self.parse_event(payload)
        slo_id = event.attributes.asset.id if event.attributes.asset else None
        if not slo_id:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if event.attributes.action == "deleted":
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
