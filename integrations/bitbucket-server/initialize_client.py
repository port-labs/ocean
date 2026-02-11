import os
from dataclasses import asdict
from typing import cast

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from client import BitbucketClient
from helpers import BitbucketClientConfig

_client: BitbucketClient | None = None
_client_pid: int | None = None


def init_client() -> BitbucketClient:
    """Initialize and return the BitbucketClient instance."""
    global _client, _client_pid
    current_pid = os.getpid()
    if _client is None or _client_pid != current_pid:
        old_rate_limiter = _client.rate_limiter if _client else None
        config = _create_config()
        _client = BitbucketClient(**asdict(config))
        if old_rate_limiter is not None:
            _client.rate_limiter._level = old_rate_limiter._level
            _client.rate_limiter._last_check = old_rate_limiter._last_check
        _client_pid = current_pid
    return _client


def _create_config() -> BitbucketClientConfig:
    integration_config = ocean.integration_config

    project_filter_regex = None
    if event.resource_config and hasattr(event.resource_config, "selector"):
        project_filter_regex = getattr(
            event.resource_config.selector, "projectFilterRegex", None
        )

    return BitbucketClientConfig(
        username=integration_config["bitbucket_username"],
        password=integration_config["bitbucket_password"],
        base_url=integration_config["bitbucket_base_url"],
        webhook_secret=integration_config.get("bitbucket_webhook_secret"),
        app_host=ocean.app.base_url,
        is_version_8_7_or_older=cast(
            bool, integration_config.get("bitbucket_is_version8_point7_or_older")
        ),
        rate_limit=int(integration_config["bitbucket_rate_limit_quota"]),
        rate_limit_window=int(integration_config["bitbucket_rate_limit_window"]),
        project_filter_regex=project_filter_regex,
    )
