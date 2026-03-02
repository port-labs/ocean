from initialize_client import create_authenticator
from port_ocean.context.ocean import ocean
from webhook.webhook_client import ServicenowWebhookClient


def initialize_webhook_client() -> ServicenowWebhookClient:
    """Initialize the webhook client."""

    authenticator = create_authenticator(
        servicenow_url=ocean.integration_config["servicenow_url"],
        client_id=ocean.integration_config.get("servicenow_client_id"),
        client_secret=ocean.integration_config.get("servicenow_client_secret"),
        username=ocean.integration_config.get("servicenow_username"),
        password=ocean.integration_config.get("servicenow_password"),
    )
    return ServicenowWebhookClient(
        servicenow_url=ocean.integration_config["servicenow_url"],
        authenticator=authenticator,
    )
