from typing import TYPE_CHECKING, Any, cast

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

if TYPE_CHECKING:
    from datadog.overrides import TeamResourceConfig

from datadog.client import DatadogClient
from datadog.core.exporters import TeamExporter
from datadog.core.exporters.team_exporter import GetTeamOptions
from datadog.webhook.consts import (
    TEAM_ACTIONS,
    AuditTrailEventName,
)
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


class TeamWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.TEAM]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#teams-management
        attrs = event.attributes
        return (
            attrs.evt.name == AuditTrailEventName.TEAMS_MANAGEMENT
            and attrs.action in TEAM_ACTIONS
        )

    async def _fetch_resource(
        self,
        client: DatadogClient,
        event: AuditTrailEvent,
        resource_config: ResourceConfig,
    ) -> dict[str, Any] | None:
        return await TeamExporter(client).get_resource(
            GetTeamOptions.from_resource_config(
                cast("TeamResourceConfig", resource_config),
                resource_id=event.attributes.asset.id,
            )
        )
