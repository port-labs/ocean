from port_ocean.context.ocean import ocean
from client import GitHubClient


def get_client() -> GitHubClient:
    """Get initialized GitHub client."""
    token = ocean.integration_config["github_access_token"]
    github_base_url = ocean.integration_config["github_base_url"]
    base_url = ocean.app.base_url

    return GitHubClient(token=token, github_base_url=github_base_url, base_url=base_url)
    