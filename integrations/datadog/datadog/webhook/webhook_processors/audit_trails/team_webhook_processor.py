import httpx
from typing import Any, cast

from integration import ObjectKind
from datadog.overrides import TeamResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
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

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not isinstance(event.payload, dict):
            return False
        e = self.parse_event(event.payload)
        return (
            e.attributes.evt.name == "Teams Management"
            and e.attributes.action in _TEAM_ACTIONS
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        event = self.parse_event(payload)
        team_id = event.attributes.asset.id if event.attributes.asset else None
        if not team_id:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if event.attributes.action == "deleted":
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
