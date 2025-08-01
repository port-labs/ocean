from typing import Any, Optional

from port_ocean.context.ocean import ocean

from github_cloud.clients.github_client import GitHubCloudClient

_github_client: Optional[GitHubCloudClient] = None


def create_github_client() -> GitHubCloudClient:
    """
    Create or return an existing GitHub Cloud client instance.

    Returns:
        GitHub Cloud client instance
    """
    global _github_client
    if _github_client is not None:
        return _github_client

    integration_config: dict[str, Any] = ocean.integration_config
    base_url = integration_config["github_host"].rstrip("/")
    _github_client = GitHubCloudClient(base_url, integration_config["github_token"])
    return _github_client
