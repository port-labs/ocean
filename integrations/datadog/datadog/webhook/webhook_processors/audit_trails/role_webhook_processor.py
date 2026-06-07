import httpx
from typing import Any

from integration import ObjectKind
from datadog.webhook.types import AuditTrailEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from datadog.core.exporters import RoleExporter
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)
from datadog.webhook.consts import (
    AuditTrailAction,
    AuditTrailEventName,
    ROLES_ACTIONS,
)


class RoleWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.ROLE]

    async def _should_process(self, event: AuditTrailEventName) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
        attrs = event.attributes
        return (
            attrs.evt.name == AuditTrailEventName.ACCESS_MANAGEMENT
            and attrs.asset.type == ObjectKind.ROLE
            and attrs.action in ROLES_ACTIONS
        )

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        role_id = event.attributes.asset.id

        if event.attributes.action == AuditTrailAction.DELETED:
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
