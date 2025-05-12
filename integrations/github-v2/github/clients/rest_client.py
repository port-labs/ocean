from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from github.clients.base_client import AbstractGithubClient
from loguru import logger
from port_ocean.utils.cache import cache_iterator_result
import re
from httpx import Response
from urllib.parse import urlparse, urlunparse


PAGE_SIZE = 100

ENDPOINTS = {
    "repository": "repos/{org}/{identifier}",
    "pull_request": "repos/{org}/{identifier}/pulls",
    "issue": "repos/{org}/{identifier}/issues",
    "team": "orgs/{org}/teams/{identifier}",
    "workflow": "repos/{org}/{identifier}/actions/workflows",
}


class GithubRestClient(AbstractGithubClient):
    """REST API implementation of GitHub client."""

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Send request to GitHub API with error handling and rate limiting."""
        url = f"{self.base_url}/{endpoint}"

        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
            )
            response.raise_for_status()

            logger.debug(f"Successfully fetched {method} {endpoint}")

            return response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Resource not found at endpoint '{endpoint}'")
                return e.response
            logger.error(
                f"GitHub API error for endpoint '{endpoint}': Status {e.response.status_code}, "
                f"Method: {method}, Response: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for endpoint '{endpoint}': {str(e)}")
            raise

    def get_next_link(self, link_header: str) -> Optional[str]:
        """
        Extracts the path and query from the 'next' link in a GitHub Link header,
        removing the leading slash.
        """

        match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        if not match:
            return None

        parsed_url = urlparse(match.group(1))
        path_and_query = urlunparse(
            ("", "", parsed_url.path, parsed_url.params, parsed_url.query, "")
        )
        return path_and_query.lstrip("/")

    async def _send_paginated_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Handle GitHub's pagination for API requests."""
        if params is None:
            params = {}

        params["per_page"] = PAGE_SIZE

        logger.info(f"Starting pagination for {method} {endpoint}")

        while True:
            response = await self._send_api_request(
                endpoint, method=method, params=params
            )
            items = response.json()
            if not items:
                return

            yield items

            # Get the Link header from the response object
            link_header = response.headers.get("Link")
            if not link_header:
                return

            next_endpoint = self.get_next_link(link_header)
            if not next_endpoint:
                return

            endpoint = next_endpoint

    async def _get_existing_webhook(self, webhook_url: str) -> Dict[str, Any] | None:
        """Return the existing webhook matching the given URL, or None if not found."""
        async for hooks in self._send_paginated_request(
            f"orgs/{self.organization}/hooks"
        ):
            existing_webhook = next(
                (hook for hook in hooks if hook["config"]["url"] == webhook_url),
                None,
            )
            if existing_webhook:
                return existing_webhook
        return None

    async def _patch_webhook(
        self, webhook_id: str, config_data: dict[str, str]
    ) -> None:

        webhook_data = {"config": config_data}

        logger.info(f"Patching webhook {webhook_id} to modify config data")
        await self._send_api_request(
            f"orgs/{self.organization}/hooks/{webhook_id}",
            method="PATCH",
            json_data=webhook_data,
        )
        logger.info(f"Successfully patched webhook {webhook_id} with secret")

    def build_webhook_config(self, webhook_url: str) -> dict[str, str]:
        config = {
            "url": webhook_url,
            "content_type": "json",
        }
        if self.webhook_secret:
            config["secret"] = self.webhook_secret
        return config

    async def create_or_update_webhook(
        self, base_url: str, webhook_events: List[str]
    ) -> None:
        """Create or update GitHub organization webhook with secret handling."""

        webhook_url = f"{base_url}/integration/webhook"

        existing_webhook = await self._get_existing_webhook(webhook_url)

        # Create new webhook with events
        if not existing_webhook:
            logger.info("Creating new GitHub webhook")
            webhook_data = {
                "name": "web",
                "active": True,
                "events": webhook_events,
                "config": self.build_webhook_config(webhook_url),
            }

            await self._send_api_request(
                f"orgs/{self.organization}/hooks", method="POST", json_data=webhook_data
            )
            logger.info("Successfully created webhook")
            return

        existing_webhook_id = existing_webhook["id"]
        existing_webhook_secret = existing_webhook["config"].get("secret")

        logger.info(f"Found existing webhook with ID: {existing_webhook_id}")

        # Check if patching is necessary
        if (self.webhook_secret and not existing_webhook_secret) or (
            not self.webhook_secret and existing_webhook_secret
        ):
            logger.info(f"Patching webhook {existing_webhook_id} to update secret")

            config_data = self.build_webhook_config(webhook_url)

            await self._patch_webhook(existing_webhook_id, config_data)
            return

        logger.info("Webhook already exists with appropriate configuration")

    async def get_single_resource(
        self, object_type: str, identifier: str
    ) -> dict[str, Any]:
        """Fetch a single resource from GitHub API."""

        if object_type not in ENDPOINTS:
            raise ValueError(f"Unsupported resource type: {object_type}")

        endpoint_template = ENDPOINTS[object_type]
        endpoint = endpoint_template.format(
            org=self.organization, identifier=identifier
        )

        response = await self._send_api_request(endpoint)
        logger.debug(f"Fetched {object_type} with identifier: {identifier}:")
        return response.json()

    @cache_iterator_result()
    async def get_repositories(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all repositories in the organization with pagination."""
        params = params or {}
        async for repos in self._send_paginated_request(
            f"orgs/{self.organization}/repos", params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.organization}"
            )
            yield repos
