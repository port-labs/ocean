import httpx
from typing import Any

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from datadog.core.exporters import UserExporter
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)

# https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
_USER_ACTIONS = frozenset({"created", "deleted", "modified"})


class UserWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.USER]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        attrs = event.attributes
        return (
            attrs.evt.name == "Access Management"
            and attrs.asset.type == ObjectKind.USER
            and attrs.action in _USER_ACTIONS
        ) or (
            # User added/removed from a role → refetch the affected user
            # https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
            attrs.evt.name == "Access Management"
            and attrs.asset.type == ObjectKind.ROLE
            and attrs.action == "modified"
            and attrs.usr is not None
            and bool(attrs.usr.uuid or attrs.usr.id)
        )

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        del resource_config
        attrs = event.attributes

        if attrs.asset.type == ObjectKind.ROLE and attrs.usr:
            user_id = attrs.usr.uuid or attrs.usr.id
        else:
            user_id = attrs.asset.id

        if not user_id:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if attrs.asset.type == ObjectKind.USER and attrs.action == "deleted":
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
