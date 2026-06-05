import httpx
from typing import Any

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from datadog.core.exporters import RoleExporter
from datadog.core.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)

# https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
_ROLE_ACTIONS = frozenset({"created", "deleted", "modified"})


class RoleWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.ROLE]

    def _should_process(self, event: AuditTrailEvent) -> bool:
        attrs = event.attributes
        return (
            attrs.evt.name == "Access Management"
            and attrs.asset.type == ObjectKind.ROLE
            and attrs.action in _ROLE_ACTIONS
        )

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        del resource_config
        role_id = event.attributes.asset.id

        if event.attributes.action == "deleted":
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
