from jira_server.webhook_processors.webhook_client import JiraWebhookClient
from port_ocean.context.ocean import ocean


def init_webhook_client() -> JiraWebhookClient:
    """Initialize and return the JiraWebhookClient instance."""
    return JiraWebhookClient(
        server_url=ocean.integration_config["jira_server_host"],
        username=ocean.integration_config.get("username"),
        password=ocean.integration_config.get("password"),
        token=ocean.integration_config.get("token"),
    )
