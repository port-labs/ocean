import re
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from github.clients.http.base_client import AbstractGithubClient
from github.helpers.utils import IgnoredError
from github.clients.rate_limiter.utils import GitHubRateLimiterConfig
from loguru import logger


PAGE_SIZE = 100


class GithubRestClient(AbstractGithubClient):
    """REST API implementation of GitHub client."""

    NEXT_PATTERN = re.compile(r'<([^>]+)>; rel="next"')

    @property
    def base_url(self) -> str:
        return self.github_host.rstrip("/")

    @property
    def rate_limiter_config(self) -> GitHubRateLimiterConfig:
        return GitHubRateLimiterConfig(
            api_type="rest",
            max_concurrent=10,
        )

    def _get_next_link(self, link_header: str) -> Optional[str]:
        """
        Extracts the URL from the 'next' link in a GitHub Link header.
        """
        match = self.NEXT_PATTERN.search(link_header)
        return match.group(1) if match else None

    async def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Handle GitHub's pagination for API requests."""
        if params is None:
            params = {}

        current_page_size = PAGE_SIZE
        current_page = 1

        logger.info(f"Starting pagination for {method} {resource}")

        while True:
            request_params = {
                **params,
                "page": current_page,
                "per_page": current_page_size,
            }
            try:
                response = await self.make_request(
                    resource,
                    method=method,
                    params=request_params,
                    ignored_errors=ignored_errors,
                )

                if not response or not (items := response.json()):
                    break

                yield items

                if not (
                    link_header := response.headers.get("Link")
                ) or not self._get_next_link(link_header):
                    break

                current_page += 1
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 500:
                    raise

                if current_page_size <= 25:
                    raise

                logger.warning(
                    f"Got 500 for {method} {resource} at page={current_page} "
                    f"per_page={current_page_size}; halving page size and retrying"
                )
                current_page = 2 * current_page - 1
                current_page_size = current_page_size // 2
