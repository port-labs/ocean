from port_ocean.core.handlers.webhook.webhook_event import EventPayload

from datadog.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)


class BaseMonitorEventsWebhookProcessor(BaseWebhookProcessor):
    @staticmethod
    def extract_monitor_id(payload: EventPayload) -> str | None:
        alert_id = payload.get("alert_id")
        if alert_id is None:
            return None
        return str(alert_id)

    @staticmethod
    def extract_service_ids(payload: EventPayload) -> list[str]:
        tags = payload.get("tags")
        if not isinstance(tags, list):
            return []

        service_ids: list[str] = []
        for tag in tags:
            if not isinstance(tag, str) or not tag.startswith("service:"):
                continue
            _, _, service_id = tag.partition(":")
            if service_id:
                service_ids.append(service_id)
        return service_ids
