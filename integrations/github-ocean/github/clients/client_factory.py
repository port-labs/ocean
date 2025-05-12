from github.clients.rest_client import GithubRestClient
from github.clients.base_client import GithubClient
from port_ocean.context.ocean import ocean


def create_github_client() -> GithubClient:
    """Create a client instance from Ocean configuration."""

    return GithubRestClient(
        token=ocean.integration_config["github_token"],
        organization=ocean.integration_config["github_organization"],
        github_host=ocean.integration_config["github_host"],
        webhook_secret=ocean.integration_config["webhook_secret"],
    )
