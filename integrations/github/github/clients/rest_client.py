from typing import Any, AsyncGenerator, Dict, List, Optional

from github.clients.base_client import AbstractGithubClient
from loguru import logger
import re
from urllib.parse import urlparse, urlunparse


PAGE_SIZE = 100


class GithubRestClient(AbstractGithubClient):
    """REST API implementation of GitHub client."""

    @property
    def base_url(self) -> str:
        return self.github_host.rstrip("/")

    def _get_next_link(self, link_header: str) -> Optional[str]:
        """
        Extracts the path and query from the 'next' link in a GitHub Link header,
        removing the leading slash.
        """

        match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        if not match:
            return None

        parsed_url = urlparse(match.group(1))
        path_and_query = urlunparse(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                parsed_url.query,
                "",
            )
        )
        return path_and_query

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
                resource, method=method, params=params
            )
            items = response.json()
            print("items", items, params)

            if not items or response.status_code == 404:
                return

            yield items

            # Get the Link header from the response object
            link_header = response.headers.get("Link")
            if not link_header:
                break

            next_resource = self._get_next_link(link_header)
            if not next_resource:
                break

            resource = next_resource
