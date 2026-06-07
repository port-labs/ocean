from typing import Any

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from datadog.core.exporters import RoleExporter
from datadog.core.exporters.role_exporter import GetRoleOptions
from datadog.webhook.consts import (
    ROLES_ACTIONS,
    AuditTrailAssetType,
    AuditTrailEventName,
)
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


class RoleWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.ROLE]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
        attrs = event.attributes
        return (
            attrs.evt.name == AuditTrailEventName.ACCESS_MANAGEMENT
            and attrs.asset.type == AuditTrailAssetType.ROLE
            and attrs.action in ROLES_ACTIONS
        )

    async def _fetch_resource(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> dict[str, Any] | None:
        return await RoleExporter(self.client).get_resource(
            GetRoleOptions(resource_id=event.attributes.asset.id)
        )
