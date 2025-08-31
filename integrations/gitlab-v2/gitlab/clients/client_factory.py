from typing import Any, Optional

from port_ocean.context.ocean import ocean

from gitlab.clients.gitlab_client import GitLabClient

_gitlab_client: Optional[GitLabClient] = None


def create_gitlab_client() -> GitLabClient:
    global _gitlab_client
    if _gitlab_client is not None:
        return _gitlab_client

    integration_config: dict[str, Any] = ocean.integration_config
    base_url = integration_config["gitlab_host"].rstrip("/")
    _gitlab_client = GitLabClient(base_url, integration_config["gitlab_token"])
    return _gitlab_client
