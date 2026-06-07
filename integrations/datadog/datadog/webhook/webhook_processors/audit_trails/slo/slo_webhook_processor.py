from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from datadog.overrides import SLOResourceConfig

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from datadog.core.exporters import SloExporter
from datadog.core.exporters.slo_exporter import GetSloOptions
from datadog.webhook.consts import (
    SLO_ACTIONS,
    AuditTrailAssetType,
    AuditTrailEventName,
)
from datadog.webhook.types import AuditTrailEvent
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

    async def _fetch_resource(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> dict[str, Any] | None:
        return await SloExporter(self.client).get_resource(
            GetSloOptions.from_resource_config(
                cast("SLOResourceConfig", resource_config),
                resource_id=event.attributes.asset.id,
            )
        )
