import httpx
from typing import TYPE_CHECKING, Any, cast

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

if TYPE_CHECKING:
    from datadog.overrides import TeamResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from datadog.core.exporters import TeamExporter
from datadog.core.exporters.team_exporter import GetTeamOptions
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)

# https://docs.datadoghq.com/account_management/audit_trail/events/#teams-management
_TEAM_ACTIONS = frozenset({"created", "deleted", "modified"})


class TeamWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.TEAM]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        attrs = event.attributes
        return attrs.evt.name == "Teams Management" and attrs.action in _TEAM_ACTIONS

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        team_id = event.attributes.asset.id

        if event.attributes.action == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": team_id}]
            )

        try:
            team = await TeamExporter(self.client).get_resource(
                GetTeamOptions.from_resource_config(
                    cast("TeamResourceConfig", resource_config), id=team_id
                )
            )
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[{"id": team_id}]
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[team] if team else [], deleted_raw_results=[]
        )
