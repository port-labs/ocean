from port_ocean.context.ocean import ocean
from github_cloud.client import GithubClient

def init_client() -> GithubClient:
    return GithubClient.create_from_ocean_config()
