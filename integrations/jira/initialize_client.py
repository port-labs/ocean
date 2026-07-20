from jira.client import JiraClient
from functools import lru_cache
from port_ocean.context.ocean import ocean


@lru_cache(maxsize=1)
def get_or_create_jira_client() -> JiraClient:
    """Create JiraClient with current configuration."""
    return JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )
