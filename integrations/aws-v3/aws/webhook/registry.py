from loguru import logger
from port_ocean.context.ocean import ocean

from aws.config.live_events import get_live_events_api_key

from aws.webhook.consts import CLOUDTRAIL_WEBHOOK_PATH
from aws.webhook.webhook_processors.cloudtrail_webhook_processor import (
    CloudTrailWebhookProcessor,
)


def register_cloudtrail_live_events() -> None:
    """Register the CloudTrail live-events processor when this instance is configured for LE."""
    if not get_live_events_api_key():
        logger.info(
            "Skipping CloudTrail live events — live_events_api_key is not configured"
        )
        return

    ocean.add_webhook_processor(CLOUDTRAIL_WEBHOOK_PATH, CloudTrailWebhookProcessor)
