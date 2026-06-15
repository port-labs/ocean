from typing import Any, cast

from datadog.overrides import OrgResourceConfig
from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from datadog.client import DatadogClient
from datadog.core.exporters import OrgExporter
from datadog.core.exporters.org_exporter import GetOrgOptions
from datadog.webhook.consts import (
    ORG_ACTIONS,
    AuditTrailAssetType,
    AuditTrailEventName,
)
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


class OrgWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.ORG]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#organization-management
        attrs = event.attributes
        return (
            attrs.evt.name == AuditTrailEventName.ORGANIZATION_MANAGEMENT
            and attrs.asset.type == AuditTrailAssetType.ORGANIZATION
            and attrs.action in ORG_ACTIONS
        )

    async def _fetch_resource(
        self,
        client: DatadogClient,
        event: AuditTrailEvent,
        resource_config: ResourceConfig,
    ) -> dict[str, Any] | None:
        return await OrgExporter(client).get_resource(
            GetOrgOptions.from_resource_config(
                cast(OrgResourceConfig, resource_config),
                resource_id=event.attributes.asset.id,
            )
        )
