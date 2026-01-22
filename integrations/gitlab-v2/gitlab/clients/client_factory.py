from typing import Any, Optional

from port_ocean.context.ocean import ocean

from gitlab.clients.gitlab_client import GitLabClient

DEFAULT_MAX_CONCURRENT_REQUESTS = 10

_gitlab_client: Optional[GitLabClient] = None


def _parse_max_concurrent(value: Any) -> int:
    """Parse max concurrent requests from config (may be string or int)."""
    if value is None:
        return DEFAULT_MAX_CONCURRENT_REQUESTS
    try:
        return int(value)
    except (ValueError, TypeError):
        return DEFAULT_MAX_CONCURRENT_REQUESTS


def create_gitlab_client() -> GitLabClient:
    global _gitlab_client
    if _gitlab_client is not None:
        return _gitlab_client

    integration_config: dict[str, Any] = ocean.integration_config
    base_url = integration_config["gitlab_host"].rstrip("/")
    max_concurrent = _parse_max_concurrent(
        integration_config.get("max_concurrent_requests")
    )

    _gitlab_client = GitLabClient(
        base_url,
        integration_config["gitlab_token"],
        max_concurrent=max_concurrent,
    )
    return _gitlab_client


def get_max_concurrent_requests() -> int:
    """Get the configured max concurrent requests value."""
    integration_config: dict[str, Any] = ocean.integration_config
    return _parse_max_concurrent(
        integration_config.get("max_concurrent_requests")
    )
