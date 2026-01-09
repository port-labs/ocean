from typing import Optional, cast

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from client import (
    BitbucketClient,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_PAGE_SIZE,
)

_global_client: Optional[BitbucketClient] = None


def get_bitbucket_client(
    username: str,
    password: str,
    base_url: str,
    webhook_secret: Optional[str],
    app_host: str,
    is_version_8_7_or_older: bool,
    rate_limit: int,
    rate_limit_window: int,
    page_size: int,
    max_concurrent_requests: int,
    project_filter_regex: Optional[str],
) -> BitbucketClient:
    global _global_client
    if _global_client is None:
        _global_client = BitbucketClient(
            username=username,
            password=password,
            base_url=base_url,
            webhook_secret=webhook_secret,
            app_host=app_host,
            is_version_8_7_or_older=is_version_8_7_or_older,
            rate_limit=rate_limit,
            rate_limit_window=rate_limit_window,
            page_size=page_size,
            max_concurrent_requests=max_concurrent_requests,
            project_filter_regex=project_filter_regex,
        )
    return _global_client


def initialize_client() -> BitbucketClient:
    config = ocean.integration_config

    project_filter_regex = None
    if event.resource_config and hasattr(event.resource_config, "selector"):
        project_filter_regex = getattr(
            event.resource_config.selector, "projectFilterRegex", None
        )

    return get_bitbucket_client(
        username=config["bitbucket_username"],
        password=config["bitbucket_password"],
        base_url=config["bitbucket_base_url"],
        webhook_secret=config.get("bitbucket_webhook_secret"),
        app_host=ocean.app.base_url,
        is_version_8_7_or_older=cast(
            bool,
            config.get("bitbucket_is_version8_point7_or_older"),
        ),
        rate_limit=int(config["bitbucket_rate_limit_quota"]),
        rate_limit_window=int(config["bitbucket_rate_limit_window"]),
        page_size=DEFAULT_PAGE_SIZE,
        max_concurrent_requests=DEFAULT_MAX_CONCURRENT_REQUESTS,
        project_filter_regex=project_filter_regex,
    )
