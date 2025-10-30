from typing import cast

from port_ocean.context.ocean import ocean

from client import (
    BitbucketClient,
    DEFAULT_BITBUCKET_RATE_LIMIT,
    DEFAULT_BITBUCKET_RATE_LIMIT_WINDOW,
    DEFAULT_PAGE_SIZE,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
)


def initialize_client() -> BitbucketClient:
    config = ocean.integration_config

    # Extract rate limiting configuration
    rate_limit = int(config.get("bitbucket_rate_limit", DEFAULT_BITBUCKET_RATE_LIMIT))
    rate_limit_window = int(
        config.get("bitbucket_rate_limit_window", DEFAULT_BITBUCKET_RATE_LIMIT_WINDOW)
    )

    # Extract pagination and concurrency configuration
    page_size = int(config.get("bitbucket_page_size", DEFAULT_PAGE_SIZE))
    max_concurrent_requests = int(
        config.get("bitbucket_max_concurrent_requests", DEFAULT_MAX_CONCURRENT_REQUESTS)
    )

    # Extract project filtering configuration
    projects_filter_regex = config.get("bitbucket_projects_filter_regex")
    projects_filter_suffix = config.get("bitbucket_projects_filter_suffix")

    return BitbucketClient(
        username=config["bitbucket_username"],
        password=config["bitbucket_password"],
        base_url=config["bitbucket_base_url"],
        webhook_secret=config.get("bitbucket_webhook_secret"),
        app_host=ocean.app.base_url,
        is_version_8_7_or_older=cast(
            bool,
            config.get("bitbucket_is_version8_point7_or_older"),
        ),
        rate_limit=rate_limit,
        rate_limit_window=rate_limit_window,
        page_size=page_size,
        max_concurrent_requests=max_concurrent_requests,
        projects_filter_regex=projects_filter_regex,
        projects_filter_suffix=projects_filter_suffix,
    )
