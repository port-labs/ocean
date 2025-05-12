from typing import Any, AsyncGenerator, List, Optional

from github.rate_limiter import GithubRateLimiter
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result


class GithubClient:

    def __init__(
        self,
        token: str,
        organization: str,
        github_host: str,
        webhook_secret: str | None,
    ) -> None:
        self.organization = organization
        self.github_host = github_host
        self.webhook_secret = webhook_secret
        self.client = http_async_client
        self.base_url = github_host.rstrip("/")

        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.client.headers.update(self.headers)
        self.rate_limiter = GithubRateLimiter()

    async def get_single_resource(
        self, object_type: str, identifier: str
    ) -> dict[str, Any]:
        """Get a single resource"""
        raise NotImplementedError("Subclasses must implement get_single_resource()")

    async def create_or_update_webhook(
        self, base_url: str, webhook_events: List[str]
    ) -> None:
        """Create webhooks if they don't exist."""
        raise NotImplementedError(
            "Subclasses must implement create_webhooks_if_not_exists()"
        )

    @cache_iterator_result()  # type: ignore
    async def get_repositories(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all repositories in the organization."""
        raise NotImplementedError("Subclasses must implement get_repositories()")
