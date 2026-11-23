from gcp_core.webhook.webhook_processors.resource_feed_processor import (
    ResourceFeedProcessor,
)
from gcp_core.webhook.webhook_processors.iam_policy_feed_processor import (
    IamPolicyFeedProcessor,
)
from port_ocean.context.ocean import ocean

WEBHOOK_PATH = "/events"


def register_webhook_processors() -> None:
    ocean.add_webhook_processor(WEBHOOK_PATH, ResourceFeedProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, IamPolicyFeedProcessor)
