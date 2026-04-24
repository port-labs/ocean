from webhook_processors.webhook_client import SentryWebhookClient
from port_ocean.context.ocean import ocean


def init_webhook_client() -> SentryWebhookClient:
    return SentryWebhookClient(
        ocean.integration_config["sentry_host"],
        ocean.integration_config["sentry_token"],
        ocean.integration_config["sentry_organization"],
    )
