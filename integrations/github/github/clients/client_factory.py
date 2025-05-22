from typing import Any, Optional

from port_ocean.context.ocean import ocean

from github.clients.github_client import GitHubClient

_github_client: Optional[GitHubClient] = None


def create_github_client() -> GitHubClient:
    """
    Create or return an existing GitHub client instance.

    Returns:
        GitHub client instance
    """
    global _github_client
    if _github_client is not None:
        return _github_client

    integration_config: dict[str, Any] = ocean.integration_config
    base_url = integration_config["github_host"].rstrip("/")
    _github_client = GitHubClient(base_url, integration_config["github_token"])
    return _github_client
