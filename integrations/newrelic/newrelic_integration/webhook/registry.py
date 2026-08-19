from port_ocean.context.ocean import ocean

from newrelic_integration.webhook.constants import WEBHOOK_PATH
from newrelic_integration.webhook.webhook_processors.entity_webhook_processor import (
    EntityWebhookProcessor,
)
from newrelic_integration.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)


def register_live_events_webhooks() -> None:
    ocean.add_webhook_processor(WEBHOOK_PATH, IssueWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, EntityWebhookProcessor)
