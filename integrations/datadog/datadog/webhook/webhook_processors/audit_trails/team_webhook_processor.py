import httpx
from typing import Any, cast

from integration import ObjectKind
from datadog.overrides import TeamResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.core.exporters import TeamExporter
from datadog.core.exporters.team_exporter import GetTeamOptions
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)

# https://docs.datadoghq.com/account_management/audit_trail/events/#teams-management
_TEAM_ACTIONS = frozenset({"created", "deleted", "modified"})


class TeamWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.TEAM]

    def _matches(self, event: dict[str, Any]) -> bool:
        return (
            self.extract_evt_name(event) == "Teams Management"
            and self.extract_action(event) in _TEAM_ACTIONS
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return isinstance(event.payload, dict) and self._matches(event.payload)

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        team_id = self.extract_asset_id(payload)
        if not team_id:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if self.is_delete_event(payload):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": team_id}]
            )

        config = cast(TeamResourceConfig, resource_config)
        try:
            team = await TeamExporter(self.client).get_resource(
                GetTeamOptions(id=team_id, include_members=config.selector.include_members)
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
