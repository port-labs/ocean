from port_ocean.context.ocean import ocean
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.webhook.webhook_processors.release_webhook_processor import (
    ReleaseWebhookProcessor,
)
from github.webhook.webhook_processors.tag_webhook_processor import TagWebhookProcessor
from github.webhook.webhook_processors.branch_webhook_processor import (
    BranchWebhookProcessor,
)


def register_live_events_webhooks() -> None:
    """Register all live event webhook processors."""
    ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
    ocean.add_webhook_processor("/webhook", ReleaseWebhookProcessor)
    ocean.add_webhook_processor("/webhook", TagWebhookProcessor)
    ocean.add_webhook_processor("/webhook", BranchWebhookProcessor)
