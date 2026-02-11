from dataclasses import dataclass

from client import DEFAULT_MAX_CONCURRENT_REQUESTS, DEFAULT_PAGE_SIZE


@dataclass
class BitbucketClientConfig:
    """Configuration for BitbucketClient initialization."""

    username: str
    password: str
    base_url: str
    webhook_secret: str | None
    app_host: str
    is_version_8_7_or_older: bool
    rate_limit: int
    rate_limit_window: int
    page_size: int = DEFAULT_PAGE_SIZE
    max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS
    project_filter_regex: str | None = None
