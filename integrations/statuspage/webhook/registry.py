from port_ocean.context.ocean import ocean

from webhook.consts import WEBHOOK_PATH
from webhook.webhook_processors.incident_update_webhook_processor import (
    IncidentUpdateWebhookProcessor,
)
from webhook.webhook_processors.incident_webhook_processor import (
    IncidentWebhookProcessor,
)
from webhook.webhook_processors.page_webhook_processor import PageWebhookProcessor


def register_live_events_webhooks() -> None:
    ocean.add_webhook_processor(WEBHOOK_PATH, PageWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, IncidentWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, IncidentUpdateWebhookProcessor)
