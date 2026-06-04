import httpx
from typing import Any

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.core.exporters import RoleExporter
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)

# https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
_ROLE_ACTIONS = frozenset({"created", "deleted", "modified"})


class RoleWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.ROLE]

    def _matches(self, event: dict[str, Any]) -> bool:
        return (
            self.extract_evt_name(event) == "Access Management"
            and self.extract_asset_type(event) == ObjectKind.ROLE
            and self.extract_action(event) in _ROLE_ACTIONS
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return isinstance(event.payload, dict) and self._matches(event.payload)

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        del resource_config
        role_id = self.extract_asset_id(payload)
        if not role_id:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if self.is_delete_event(payload):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": role_id}]
            )

        try:
            role = await RoleExporter(self.client).get_resource(role_id)
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[{"id": role_id}]
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[role] if role else [], deleted_raw_results=[]
        )
