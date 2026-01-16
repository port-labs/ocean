from jira_server.client import JiraServerClient
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
