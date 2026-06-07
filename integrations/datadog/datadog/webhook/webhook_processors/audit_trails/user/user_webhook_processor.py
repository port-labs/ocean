from typing import Any

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from datadog.core.exporters import UserExporter
from datadog.webhook.consts import (
    USER_ACTIONS,
    AuditTrailAssetType,
    AuditTrailEventName,
)
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


class UserWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.USER]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
        attrs = event.attributes
        return (
            attrs.evt.name == AuditTrailEventName.ACCESS_MANAGEMENT
            and attrs.asset.type == AuditTrailAssetType.USER
            and attrs.action in USER_ACTIONS
            # http path distinguishes user CRUD from role-membership events
            and attrs.http is not None
            and not attrs.http.url_details.path.startswith("/api/v2/roles")
        )

    async def _fetch_resource(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> dict[str, Any] | None:
        return await UserExporter(self.client).get_resource(event.attributes.asset.id)
