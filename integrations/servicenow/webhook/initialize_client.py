from initialize_client import create_authenticator
from port_ocean.context.ocean import ocean
from webhook.webhook_client import ServicenowWebhookClient


def initialize_webhook_client() -> ServicenowWebhookClient:
    """Initialize the webhook client."""

    authenticator = create_authenticator()
    return ServicenowWebhookClient(
        servicenow_url=ocean.integration_config["servicenow_url"],
        authenticator=authenticator,
    )
