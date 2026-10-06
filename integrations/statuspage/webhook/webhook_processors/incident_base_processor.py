from typing import Any

from port_ocean.core.handlers.webhook.webhook_event import EventPayload
from webhook.consts import WebhookPayloadKey
from webhook.webhook_processors.base_webhook_processor import BaseWebhookProcessor


class BaseIncidentWebhookProcessor(BaseWebhookProcessor):
    @staticmethod
    def get_incident(payload: EventPayload) -> dict[str, Any] | None:
        incident = payload.get(WebhookPayloadKey.INCIDENT)
        if not isinstance(incident, dict):
            return None
        return incident
