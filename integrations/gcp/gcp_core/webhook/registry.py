from gcp_core.webhook.webhook_processors.asset_feed_processor import AssetFeedProcessor
from gcp_core.webhook.webhook_processors.iam_policy_feed_processor import (
    IamPolicyFeedProcessor,
)
from port_ocean.context.ocean import ocean

WEBHOOK_PATH = "/events"


def register_webhook_processors() -> None:
    ocean.add_webhook_processor(WEBHOOK_PATH, AssetFeedProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, IamPolicyFeedProcessor)
