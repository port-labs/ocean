import httpx
from typing import Any

from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from datadog.core.exporters import MonitorExporter
from datadog.core.exporters.monitor_exporter import GetMonitorOptions
from datadog.core.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)

# https://docs.datadoghq.com/account_management/audit_trail/events/#monitor
_MONITOR_ACTIONS = frozenset({"created", "modified", "deleted"})

# https://docs.datadoghq.com/account_management/audit_trail/events/#access-management
_RESTRICTION_POLICY_ACTIONS = frozenset({"modified", "deleted"})


class MonitorWebhookProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return [ObjectKind.MONITOR]

    @staticmethod
    def _monitor_id_from_restriction_policy(event: AuditTrailEvent) -> str | None:
        """Return the monitor ID embedded in a restriction_policy asset ID (e.g. 'monitor:12345')."""
        asset_id = event.attributes.asset.id
        if ":" in asset_id:
            resource_type, resource_id = asset_id.split(":", 1)
            return resource_id if resource_type == ObjectKind.MONITOR else None
        return None

    @classmethod
    def _is_restriction_policy_for_monitor(cls, event: AuditTrailEvent) -> bool:
        return (
            event.attributes.asset.type == "restriction_policy"
            and cls._monitor_id_from_restriction_policy(event) is not None
        )

    @staticmethod
    def _should_include_restriction_policy(resource_config: ResourceConfig) -> bool:
        if isinstance(resource_config, dict):
            selector = resource_config.get("selector")
            return bool(
                selector.get("include_restriction_policy", False)
                if isinstance(selector, dict)
                else False
            )
        return bool(
            getattr(getattr(resource_config, "selector", None), "include_restriction_policy", False)
        )

    def _should_process(self, event: AuditTrailEvent) -> bool:
        attrs = event.attributes
        return (
            attrs.evt.name == "Monitor"
            and attrs.asset.type == ObjectKind.MONITOR
            and attrs.action in _MONITOR_ACTIONS
        ) or (
            attrs.evt.name == "Access Management"
            and self._is_restriction_policy_for_monitor(event)
            and attrs.action in _RESTRICTION_POLICY_ACTIONS
        )

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        if self._is_restriction_policy_for_monitor(event):
            monitor_id = self._monitor_id_from_restriction_policy(event)
        else:
            monitor_id = event.attributes.asset.id

        if not monitor_id:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if (
            event.attributes.asset.type == ObjectKind.MONITOR
            and event.attributes.action == "deleted"
        ):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[{"id": monitor_id}]
            )

        try:
            monitor = await MonitorExporter(self.client).get_resource(
                GetMonitorOptions(
                    resource_id=monitor_id,
                    include_restriction_policy=self._should_include_restriction_policy(
                        resource_config
                    ),
                )
            )
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[{"id": monitor_id}]
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[monitor] if monitor else [], deleted_raw_results=[]
        )
