from typing import Any

from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from datadog.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)


class BaseProcessor(BaseWebhookProcessor):
    @staticmethod
    def _extract_wrapped_event(payload: EventPayload) -> dict[str, Any]:
        for key in ("event", "data"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        return payload

    @classmethod
    def extract_asset_type(cls, payload: EventPayload) -> str | None:
        event = cls._extract_wrapped_event(payload)
        asset = event.get("asset")
        if isinstance(asset, dict):
            asset_type = asset.get("type")
            if asset_type is not None:
                return str(asset_type).lower()
        return None

    @classmethod
    def extract_asset_id(cls, payload: EventPayload) -> str | None:
        event = cls._extract_wrapped_event(payload)
        asset = event.get("asset")
        if isinstance(asset, dict):
            asset_id = asset.get("id")
            if asset_id is not None:
                return str(asset_id)
        return None

    @classmethod
    def is_delete_event(cls, payload: EventPayload) -> bool:
        event = cls._extract_wrapped_event(payload)
        action = str(event.get("action", "")).lower()
        return any(token in action for token in ("delete", "remove", "destroy"))

    @classmethod
    def _is_supported_audit_action(cls, payload: EventPayload) -> bool:
        event = cls._extract_wrapped_event(payload)
        action = str(event.get("action", "")).lower()
        if not action:
            return False
        return any(
            token in action
            for token in (
                "create",
                "update",
                "delete",
                "add",
                "remove",
                "modify",
                "change",
                "grant",
                "revoke",
                "assign",
                "unassign",
            )
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return self._is_supported_audit_action(event.payload)
