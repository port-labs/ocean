from typing import Any, Optional
from port_ocean.context.ocean import ocean
from .github_client import GitHubClient

_github_client: Optional[GitHubClient] = None


def create_github_client() -> GitHubClient:
    global _github_client
    if _github_client is not None:
        return _github_client

    integration_config: dict[str, Any] = ocean.integration_config
    _github_client = GitHubClient(
        integration_config["github_host"], integration_config["github_token"]
    )
    return _github_client
