import httpx
from typing import Any

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.core.exporters import UserExporter
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)

# https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
_USER_ACTIONS = frozenset({"created", "deleted", "modified"})


class UserWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.USER]

    @classmethod
    def _user_id_from_role_event(cls, event: dict[str, Any]) -> str | None:
        """Extract the affected user's ID from a role:modified membership-change event."""
        usr = cls._attrs(event).get("usr")
        if not isinstance(usr, dict):
            return None
        return str(usr.get("uuid") or usr.get("id") or "") or None

    def _matches(self, event: dict[str, Any]) -> bool:
        return (
            self.extract_evt_name(event) == "Access Management"
            and self.extract_asset_type(event) == ObjectKind.USER
            and self.extract_action(event) in _USER_ACTIONS
        ) or (
            # User added/removed from a role → refetch the affected user
            # https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
            self.extract_evt_name(event) == "Access Management"
            and self.extract_asset_type(event) == ObjectKind.ROLE
            and self.extract_action(event) == "modified"
            and self._user_id_from_role_event(event) is not None
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return isinstance(event.payload, dict) and self._matches(event.payload)

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not isinstance(payload, dict) or not self._matches(payload):
            return False
        if self.extract_asset_type(payload) == ObjectKind.ROLE:
            return self._user_id_from_role_event(payload) is not None
        return self.extract_asset_id(payload) is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        del resource_config

        if self.extract_asset_type(payload) == ObjectKind.ROLE:
            user_id = self._user_id_from_role_event(payload)
        else:
            user_id = self.extract_asset_id(payload)

        if not user_id:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if self.extract_asset_type(payload) == ObjectKind.USER and self.is_delete_event(payload):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": user_id}]
            )

        try:
            user = await UserExporter(self.client).get_resource(user_id)
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[{"id": user_id}]
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[user] if user else [], deleted_raw_results=[]
        )
