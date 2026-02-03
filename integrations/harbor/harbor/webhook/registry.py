"""Registry for Harbor webhook processors."""

from port_ocean.context.ocean import ocean
from harbor.webhook.webhook_processors.artifact_webhook_processor import (
    ArtifactWebhookProcessor,
)
from harbor.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)


def register_harbor_webhooks(path: str = "/webhook") -> None:
    """Register all Harbor webhook processors."""
    ocean.add_webhook_processor(path, ArtifactWebhookProcessor)
    ocean.add_webhook_processor(path, RepositoryWebhookProcessor)
