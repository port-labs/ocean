from port_ocean.context.ocean import ocean

from aws.live_events.handler import AWSWebhookProcessor

WEBHOOK_PATH = "/webhook"


def register_webhook_processors() -> None:
    """Register all AWS live event webhook processors with the Ocean router."""
    ocean.add_webhook_processor(WEBHOOK_PATH, AWSWebhookProcessor)
