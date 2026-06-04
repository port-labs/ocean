from typing import Any

from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from datadog.client import DatadogClient
from datadog.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)
from initialize_client import init_client


class BaseAuditTrailProcessor(BaseWebhookProcessor):
    """Shared helpers for audit-trail processors.

    Each WebhookEvent carries exactly one event dict — batches are split
    upstream by DatadogLiveEventsProcessorManager.
    """

    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self.client: DatadogClient = init_client()

    @staticmethod
    def _attrs(event: dict[str, Any]) -> dict[str, Any]:
        attrs = event.get("attributes")
        return attrs if isinstance(attrs, dict) else event

    @classmethod
    def extract_evt_name(cls, event: dict[str, Any]) -> str:
        return str(cls._attrs(event).get("evt", {}).get("name", "")).strip()

    @classmethod
    def extract_action(cls, event: dict[str, Any]) -> str:
        return str(cls._attrs(event).get("action", "")).lower()

    @classmethod
    def extract_asset_type(cls, event: dict[str, Any]) -> str | None:
        asset = cls._attrs(event).get("asset")
        if isinstance(asset, dict):
            t = asset.get("type")
            return str(t).lower() if t is not None else None
        return None

    @classmethod
    def extract_asset_id(cls, event: dict[str, Any]) -> str | None:
        asset = cls._attrs(event).get("asset")
        if isinstance(asset, dict):
            asset_id = asset.get("id")
            return str(asset_id) if asset_id is not None else None
        return None

    @classmethod
    def is_delete_event(cls, event: dict[str, Any]) -> bool:
        return cls.extract_action(event) == "deleted"

    async def validate_payload(self, payload: EventPayload) -> bool:
        return (
            isinstance(payload, dict)
            and self._matches(payload)
            and self.extract_asset_id(payload) is not None
        )

    def _matches(self, event: dict[str, Any]) -> bool:  # pragma: no cover
        raise NotImplementedError
