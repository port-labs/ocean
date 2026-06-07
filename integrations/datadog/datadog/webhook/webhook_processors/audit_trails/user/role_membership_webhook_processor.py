import re
from typing import Any

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from datadog.core.exporters import UserExporter
from datadog.webhook.consts import (
    AuditTrailAction,
    AuditTrailAssetType,
    AuditTrailEventName,
)
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)

_TARGET_USER_PATTERN = re.compile(
    r'(?:added|removed)\s+user\s+"([^@"]+@[^"]+)"', re.IGNORECASE
)


def _extract_target_user_email(msg: str | None) -> str | None:
    """Extract the target user email from a role-membership audit message.

    Example message:
        omrib@getport.io successfully removed user "omrib@getport.io" from the role "Datadog Read Only Role"
    """
    if not msg:
        return None
    match = _TARGET_USER_PATTERN.search(msg)
    return match.group(1) if match else None


class RoleMembershipWebhookProcessor(BaseAuditTrailProcessor):
    """Handles Access Management events where a user is added to or removed from a role."""

    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.USER]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        # https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
        attrs = event.attributes
        if not (
            attrs.evt.name == AuditTrailEventName.ACCESS_MANAGEMENT
            # Docs say asset type in this case should be role, but it's user
            and attrs.asset.type == AuditTrailAssetType.USER
            and attrs.action == AuditTrailAction.MODIFIED
            # This is the only indication that this is role membership event
            # rather than user crud event
            and attrs.http is not None
            and attrs.http.url_details.path.startswith("/api/v2/roles")
        ):
            return False
        return _extract_target_user_email(attrs.msg) is not None

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        del resource_config
        email = _extract_target_user_email(event.attributes.msg)

        if not email:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        user = await UserExporter(self.client).get_resource_by_email(email)
        return WebhookEventRawResults(
            updated_raw_results=[user] if user else [], deleted_raw_results=[]
        )
