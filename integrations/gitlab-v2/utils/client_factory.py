from enum import StrEnum
from typing import Any, Optional
from clients.gitlab_client import GitLabClient
from port_ocean.context.ocean import ocean

_gitlab_client: Optional[GitLabClient] = None


def create_gitlab_client() -> GitLabClient:
    global _gitlab_client
    if _gitlab_client is not None:
        return _gitlab_client

    integration_config: dict[str, Any] = ocean.integration_config
    base_url = integration_config["gitlab_host"].rstrip("/")
    _gitlab_client = GitLabClient(base_url, integration_config["gitlab_token"])
    return _gitlab_client
