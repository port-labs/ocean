from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from github.clients.base_client import GithubClient
from loguru import logger
from port_ocean.utils.cache import cache_iterator_result


PAGE_SIZE = 100


class GithubRestClient(GithubClient):
    """REST API implementation of GitHub client."""

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send request to GitHub API with error handling and rate limiting."""
        url = f"{self.base_url}/{endpoint}"

        async with self.rate_limiter:
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                )
                response.raise_for_status()

                logger.debug(f"Successfully fetched {method} {endpoint}")

                # Update rate limit info
                self.rate_limiter.update_rate_limit(response.headers)
                return response.json() if response.text else {}

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.debug(f"Resource not found at endpoint '{endpoint}'")
                    return {}
                logger.error(
                    f"GitHub API error for endpoint '{endpoint}': Status {e.response.status_code}, "
                    f"Method: {method}, Response: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP error for endpoint '{endpoint}': {str(e)}")
                raise

    async def _paginate_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Handle GitHub's pagination for API requests."""
        if params is None:
            params = {}

        params["per_page"] = PAGE_SIZE
        page = 1

        logger.info(f"Starting pagination for {method} {endpoint}")

        try:
            while True:
                params["page"] = page
                response = await self._send_api_request(
                    endpoint, method=method, params=params
                )

                if not response:
                    return

                items = (
                    response
                    if isinstance(response, list)
                    else response.get("items", [])
                )

                if not items:
                    return

                yield items

                # Check for next page in Link header
                if isinstance(response, dict) and not response.get("next"):
                    return
                page += 1
        except StopAsyncIteration:
            logger.debug(f"Pagination stopped for {method} {endpoint}")

    async def _patch_webhook(
        self, webhook_url: str, webhook_id: str, webhook_secret: str
    ) -> None:
        """Patch a webhook to add a secret."""

        webhook_data = {
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": webhook_secret,
            },
        }

        logger.info(f"Patching webhook {webhook_id} to add secret")
        await self._send_api_request(
            f"orgs/{self.organization}/hooks/{webhook_id}",
            method="PATCH",
            json_data=webhook_data,
        )
        logger.info(f"Successfully patched webhook {webhook_id} with secret")

    async def create_or_update_webhook(
        self, base_url: str, webhook_events: List[str]
    ) -> None:
        """Create or update GitHub organization webhook with secret handling."""

        webhook_url = f"{base_url}/integration/webhook"

        existing_webhook = None
        async for hooks in self._paginate_request(f"orgs/{self.organization}/hooks"):
            existing_webhook = next(
                (hook for hook in hooks if hook["config"].get("url") == webhook_url),
                None,
            )
            if existing_webhook:
                break

        # Create new webhook with all events
        if not existing_webhook:
            logger.info("Creating new GitHub webhook")
            webhook_data = {
                "name": "web",
                "active": True,
                "events": webhook_events,
                "config": {
                    "url": webhook_url,
                    "content_type": "json",
                    **({"secret": self.webhook_secret} if self.webhook_secret else {}),
                },
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

            await self._patch_webhook(
                webhook_url, existing_webhook_id, self.webhook_secret
            )
            return

        logger.info("Webhook already exists with appropriate configuration")

    async def get_single_resource(
        self, object_type: str, identifier: str
    ) -> dict[str, Any]:
        """Fetch a single resource from GitHub API."""

        endpoints = {
            "repository": f"repos/{self.organization}/{identifier}",
            "pull_request": f"repos/{self.organization}/{identifier}/pulls",
            "issue": f"repos/{self.organization}/{identifier}/issues",
            "team": f"orgs/{self.organization}/teams/{identifier}",
            "workflow": f"repos/{self.organization}/{identifier}/actions/workflows",
        }

        if object_type not in endpoints:
            raise ValueError(f"Unsupported resource type: {object_type}")

        endpoint = endpoints[object_type]
        response = await self._send_api_request(endpoint)
        logger.debug(f"Fetched {object_type} {identifier}: {response}")
        return response

    @cache_iterator_result()
    async def get_repositories(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all repositories in the organization with pagination."""
        params = params or {}
        async for repos in self._paginate_request(
            f"orgs/{self.organization}/repos", params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.organization}"
            )
            yield repos
