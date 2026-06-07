import httpx
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from datadog.overrides import SLOResourceConfig

from integration import ObjectKind
from datadog.webhook.consts import (
    AuditTrailAction,
    AuditTrailAssetType,
    AuditTrailEventName,
    SLO_ACTIONS,
)
from datadog.webhook.types import AuditTrailEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from datadog.core.exporters import SloExporter
from datadog.core.exporters.slo_exporter import GetSloOptions
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


class SloWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.SLO]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#service-level-objectives
        attrs = event.attributes
        return (
            attrs.evt.name == AuditTrailEventName.SLO
            and attrs.asset.type == AuditTrailAssetType.SLO
            and attrs.action in SLO_ACTIONS
        )

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        slo_id = event.attributes.asset.id

        if event.attributes.action == AuditTrailAction.DELETED:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": slo_id}]
            )

        try:
            slo = await SloExporter(self.client).get_resource(
                GetSloOptions.from_resource_config(
                    cast("SLOResourceConfig", resource_config), id=slo_id
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
