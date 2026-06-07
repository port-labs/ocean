from typing import Any

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from datadog.core.exporters import UserExporter
from datadog.webhook.consts import (
    ROLES_ACTIONS,
    AuditTrailAssetType,
    AuditTrailEventName,
)
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


class RoleMembershipWebhookProcessor(BaseAuditTrailProcessor):
    """Handles Access Management events where a user is added to or removed from a role."""

    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.USER]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
        attrs = event.attributes
        return (
            attrs.evt.name == AuditTrailEventName.ACCESS_MANAGEMENT
            and attrs.asset.type == AuditTrailAssetType.ROLE
            and attrs.action in ROLES_ACTIONS
            and attrs.usr is not None
            and attrs.usr.uuid is not None
        )

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        del resource_config
        user_uuid = event.attributes.usr.uuid if event.attributes.usr else None

        if not user_uuid:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        user = await UserExporter(self.client).get_resource(user_uuid)

        return WebhookEventRawResults(
            updated_raw_results=[user] if user else [], deleted_raw_results=[]
        )
