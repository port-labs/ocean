from typing import TYPE_CHECKING, Any, cast

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

if TYPE_CHECKING:
    from datadog.overrides import MonitorResourceConfig

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
    """Handles Access Management events where a restriction policy wrapping a monitor changes.

    When the restriction policy is deleted the monitor itself still exists, so
    _deleted_result returns None to bypass the delete branch and re-fetch instead.
    """

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

    def _deleted_result(self, event: AuditTrailEvent) -> dict[str, Any] | None:
        return None  # restriction deleted ≠ monitor deleted; re-fetch instead

    async def _fetch_resource(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> dict[str, Any] | None:
        asset = parse_restriction_policy_asset(event.attributes.asset.id)
        if not asset:
            return None
        return await MonitorExporter(self.client).get_resource(
            GetMonitorOptions.from_resource_config(
                cast("MonitorResourceConfig", resource_config),
                id=asset.id,
            )
        )
