from typing import Optional

from port_ocean.context.ocean import ocean

from github.clients.github_client import GitHubClient

from loguru import logger

_github_client: Optional[GitHubClient] = None


def create_github_client() -> GitHubClient:
    global _github_client
    if _github_client is not None:
        return _github_client

    integration_config = ocean.integration_config
    base_url = integration_config.get("github_host", "https://api.github.com").rstrip(
        "/"
    )
    _github_client = GitHubClient(base_url, integration_config.get("github_token"))
    return _github_client
