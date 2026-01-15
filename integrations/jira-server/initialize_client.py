from jira_server.client import JiraServerClient
from jira_server.webhook_processors.webhook_client import JiraWebhookClient
from port_ocean.context.ocean import ocean


def create_jira_server_client() -> JiraServerClient:
    """Create JiraClient with current configuration."""
    config = ocean.integration_config

    # Try token first, fall back to username/password if token is not available
    if config.get("token"):
        return JiraServerClient(
            server_url=config["jira_server_host"],
            token=config["token"],
        )
    elif config.get("username") and config.get("password"):
        return JiraServerClient(
            server_url=config["jira_server_host"],
            username=config["username"],
            password=config["password"],
        )
    else:
        raise ValueError(
            "Either token or both username and password must be provided in the configuration"
        )


def init_webhook_client() -> JiraWebhookClient:
    """Initialize and return the JiraWebhookClient instance."""
    return JiraWebhookClient(
        server_url=ocean.integration_config["jira_host"],
        token=ocean.integration_config.get("jira_token"),
        username=ocean.integration_config.get("jira_username"),
        password=ocean.integration_config.get("jira_password"),
    )
