from jira_server.client import JiraServerClient
from port_ocean.context.ocean import ocean


def create_jira_server_client() -> JiraServerClient:
    """Create JiraClient with current configuration."""
    return JiraServerClient(
        ocean.integration_config["jira_server_host"],
        ocean.integration_config["username"],
        ocean.integration_config["password"],
    )
