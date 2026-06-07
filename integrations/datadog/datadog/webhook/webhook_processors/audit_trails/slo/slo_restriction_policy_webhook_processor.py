from typing import TYPE_CHECKING, Any, cast

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

if TYPE_CHECKING:
    from datadog.overrides import SLOResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from datadog.core.exporters import SloExporter
from datadog.core.exporters.slo_exporter import GetSloOptions
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


class SloRestrictionPolicyWebhookProcessor(BaseAuditTrailProcessor):
    """Handles Access Management events where a restriction policy wrapping an SLO changes."""

    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.SLO]

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
        return asset is not None and asset.type == AuditTrailAssetType.SLO

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        asset = parse_restriction_policy_asset(event.attributes.asset.id)
        slo_id = asset.id if asset else None

        if not slo_id:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        slo = await SloExporter(self.client).get_resource(
            GetSloOptions.from_resource_config(
                cast("SLOResourceConfig", resource_config),
                id=slo_id,
            )
        )

        return WebhookEventRawResults(
            updated_raw_results=[slo] if slo else [], deleted_raw_results=[]
        )
