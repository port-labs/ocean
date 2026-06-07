from typing import TYPE_CHECKING, Any, cast

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

if TYPE_CHECKING:
    from datadog.overrides import MonitorResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from datadog.core.exporters import MonitorExporter
from datadog.core.exporters.monitor_exporter import GetMonitorOptions
from datadog.utils import parse_restriction_policy_asset
from datadog.webhook.consts import (
    RESTRICTION_POLICY_ACTIONS,
    AuditTrailAssetType,
    AuditTrailEventName,
)
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


class MonitorRestrictionPolicyWebhookProcessor(BaseAuditTrailProcessor):
    """Handles Access Management events where a restriction policy wrapping a monitor changes."""

    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.MONITOR]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
        attrs = event.attributes
        if not (
            attrs.evt.name == AuditTrailEventName.ACCESS_MANAGEMENT
            and attrs.asset.type == AuditTrailAssetType.RESTRICTION_POLICY
            and attrs.action in RESTRICTION_POLICY_ACTIONS
        ):
            return False
        asset = parse_restriction_policy_asset(attrs.asset.id)
        return asset is not None and asset.type == AuditTrailAssetType.MONITOR

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        asset = parse_restriction_policy_asset(event.attributes.asset.id)
        monitor_id = asset.id if asset else None

        if not monitor_id:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        monitor = await MonitorExporter(self.client).get_resource(
            GetMonitorOptions.from_resource_config(
                cast("MonitorResourceConfig", resource_config),
                id=monitor_id,
            )
        )

        return WebhookEventRawResults(
            updated_raw_results=[monitor] if monitor else [], deleted_raw_results=[]
        )
