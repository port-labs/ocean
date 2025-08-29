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

    # Get access config values (always exists due to default in integration.py)
    access_config = integration_config["accessConfig"]
    use_min_access_level = access_config["useMinAccessLevel"]
    min_access_level = access_config["minAccessLevel"]

    # Build default params based on configuration
    default_params = {"all_available": True}
    if use_min_access_level:
        default_params["min_access_level"] = min_access_level

    _gitlab_client = GitLabClient(
        base_url, integration_config["gitlab_token"], default_params
    )
    return _gitlab_client
