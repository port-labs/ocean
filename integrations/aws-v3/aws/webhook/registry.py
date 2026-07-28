from port_ocean.context.ocean import ocean

from aws.webhook.consts import CLOUDTRAIL_WEBHOOK_PATH
from aws.webhook.webhook_processors.cloudtrail_webhook_processor import (
    CloudTrailWebhookProcessor,
)


def register_live_events_webhooks() -> None:
    ocean.add_webhook_processor(CLOUDTRAIL_WEBHOOK_PATH, CloudTrailWebhookProcessor)
