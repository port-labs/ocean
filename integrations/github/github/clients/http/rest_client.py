from typing import Any, AsyncGenerator, Dict, List, Optional

from github.clients.http.base_client import AbstractGithubClient
from loguru import logger
import re


PAGE_SIZE = 100


class GithubRestClient(AbstractGithubClient):
    """REST API implementation of GitHub client."""

    @property
    def base_url(self) -> str:
        return self.github_host.rstrip("/")

    def _has_next_page(self, link_header: str) -> bool:
        """
        Check if there's a next page in the GitHub Link header.
        """
        return bool(re.search(r'<([^>]+)>;\s*rel="next"', link_header))

    async def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Handle GitHub's pagination for API requests."""
        if params is None:
            params = {}

        params["per_page"] = PAGE_SIZE

        logger.info(f"Starting pagination for {method} {resource}")

        while True:
            response = await self.send_api_request(
                resource, method=method, params=params, return_full_response=True
            )

            if not response or not (items := response.json()):
                break

            yield items

            if not (
                link_header := response.headers.get("Link")
            ) or not self._has_next_page(link_header):
                break

            params["page"] = params.get("page", 1) + 1
