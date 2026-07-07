from port_ocean.context.ocean import ocean

from webhook.webhook_processors.environment_webhook_processor import (
    EnvironmentWebhookProcessor,
)
from webhook.webhook_processors.incident_webhook_processor import (
    IncidentWebhookProcessor,
)
from webhook.webhook_processors.retrospective_webhook_processor import (
    RetrospectiveWebhookProcessor,
)
from webhook.webhook_processors.service_webhook_processor import (
    ServiceWebhookProcessor,
)

WEBHOOK_PATH = "/webhook"


def register_live_events_webhooks() -> None:
    ocean.add_webhook_processor(WEBHOOK_PATH, IncidentWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, RetrospectiveWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, EnvironmentWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, ServiceWebhookProcessor)
