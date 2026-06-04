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

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not isinstance(event.payload, dict):
            return False
        e = self.parse_event(event.payload)
        attrs = e.attributes
        return (
            attrs.evt.name == "Access Management"
            and attrs.asset is not None
            and attrs.asset.type == ObjectKind.USER
            and attrs.action in _USER_ACTIONS
        ) or (
            # User added/removed from a role → refetch the affected user
            # https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
            attrs.evt.name == "Access Management"
            and attrs.asset is not None
            and attrs.asset.type == ObjectKind.ROLE
            and attrs.action == "modified"
            and attrs.usr is not None
            and bool(attrs.usr.uuid or attrs.usr.id)
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not isinstance(payload, dict):
            return False
        event = self.parse_event(payload)
        attrs = event.attributes
        if attrs.asset and attrs.asset.type == ObjectKind.ROLE:
            return attrs.usr is not None and bool(attrs.usr.uuid or attrs.usr.id)
        return attrs.asset is not None and attrs.asset.id is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        del resource_config
        event = self.parse_event(payload)
        attrs = event.attributes

        if attrs.asset and attrs.asset.type == ObjectKind.ROLE and attrs.usr:
            user_id = attrs.usr.uuid or attrs.usr.id
        else:
            user_id = attrs.asset.id if attrs.asset else None

        if not user_id:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if attrs.asset and attrs.asset.type == ObjectKind.USER and attrs.action == "deleted":
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
