from port_ocean.context.ocean import ocean
from github.client import GitHubClient


def create_github_client() -> GitHubClient:
    config = ocean.integration_config
    return GitHubClient(token=config["github_token"], org=config["github_org"])
