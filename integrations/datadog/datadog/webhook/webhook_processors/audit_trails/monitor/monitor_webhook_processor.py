from typing import TYPE_CHECKING, Any, cast

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

if TYPE_CHECKING:
    from datadog.overrides import MonitorResourceConfig

from datadog.core.exporters import MonitorExporter
from datadog.core.exporters.monitor_exporter import GetMonitorOptions
from datadog.webhook.consts import (
    MONITOR_ACTIONS,
    AuditTrailAssetType,
    AuditTrailEventName,
)
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


class AuditMonitorWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.MONITOR]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#monitor
        attrs = event.attributes
        return (
            attrs.evt.name == AuditTrailEventName.MONITOR
            and attrs.asset.type == AuditTrailAssetType.MONITOR
            and attrs.action in MONITOR_ACTIONS
        )

    async def _fetch_resource(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> dict[str, Any] | None:
        return await MonitorExporter(self.client).get_resource(
            GetMonitorOptions.from_resource_config(
                cast("MonitorResourceConfig", resource_config),
                resource_id=event.attributes.asset.id,
            )
        )
