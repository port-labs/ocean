import asyncio
from typing import AsyncGenerator, Optional, Dict, Any
from loguru import logger
from aiolimiter import AsyncLimiter
import httpx
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.context.ocean import ocean


class GitHubClient:
    """Client for interacting with the GitHub API."""

    PAGE_SIZE = 100
    MAX_RATE_LIMIT = 5000
    TIME_WINDOW = 3600

    def __init__(
        self,
        token: str,
        github_base_url: str = "https://api.github.com",
        base_url: str | None = None,
    ):
        self.token = token
        self.github_base_url = github_base_url
        self.base_url = base_url
        self.rate_limiter = AsyncLimiter(self.MAX_RATE_LIMIT, self.TIME_WINDOW)
        self.client = http_async_client

    async def _handle_rate_limit(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            logger.warning(
                f"Github API rate limit reached. Waiting for {response.headers['Retry-After']} seconds."
            )
            await asyncio.sleep(int(response.headers["Retry-After"]))

    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            async with self.rate_limiter:
                response = await self.client.request(
                    method=method, url=url, params=params, json=json, headers=headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            await self._handle_rate_limit(e.response)
            logger.error(
                f"Github API request failed with status {e.response.status_code}: {method} {url}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to Github API: {method} {url} - {str(e)}")
            raise

    async def _fetch_paginated_api(
        self, url: str, method: str, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated data from GitHub API."""
        page = 1
        per_page = self.PAGE_SIZE

        while True:
            query_params = {"page": page, "per_page": per_page}
            if params:
                query_params.update(params)

            response = await self._send_api_request(method, url, params=query_params)
            data = response.json()

            if not data:
                break

            yield data

            if len(data) < per_page:
                break

            page += 1

    async def get_organizations(self, organizations: list[str]) -> list[dict[str, Any]]:
        """Get organization details."""
        organization_tasks = [
            self._send_api_request("GET", f"{self.github_base_url}/orgs/{organization}")
            for organization in organizations
        ]
        orgs = []
        for response in await asyncio.gather(*organization_tasks):
            orgs.append(response)
        return orgs

    @cache_iterator_result()
    async def get_repositories(
        self, organizations: list[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List repositories."""
        repository_tasks = [
            self._send_api_request(
                "GET", f"{self.github_base_url}/orgs/{organization}/repos"
            )
            for organization in organizations
        ]
        async for repos in stream_async_iterators_tasks(*repository_tasks):
            yield repos

    async def get_pull_requests(
        self, organizations: list[str], state: str = "all"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List pull requests."""
        async for repos in self.get_repositories(organizations):
            for repo in repos:
                prs = await self._send_api_request(
                    "GET",
                    f"{self.github_base_url}/repos/{repo['owner']['login']}/{repo['name']}/pulls",
                    params={"state": state},
                )
                if prs:
                    yield prs

    async def get_issues(
        self, organizations: list[str], state: str = "all"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List issues."""
        async for repos in self.get_repositories(organizations):
            for repo in repos:
                issues = await self._send_api_request(
                    "GET",
                    f"{self.github_base_url}/repos/{repo['owner']['login']}/{repo['name']}/issues",
                    params={"state": state},
                )
                if issues:
                    yield issues

    async def get_teams(
        self, organizations: list[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List teams."""
        team_tasks = [
            self._send_api_request(
                "GET", f"{self.github_base_url}/orgs/{organization}/teams"
            )
            for organization in organizations
        ]
        async for teams in stream_async_iterators_tasks(*team_tasks):
            yield teams

    async def get_workflows(
        self, organizations: list[str], state: str = "active"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List workflows."""
        async for repos in self.get_repositories(organizations):
            for repo in repos:
                workflows = await self._send_api_request(
                    "GET",
                    f"{self.github_base_url}/repos/{repo['owner']['login']}/{repo['name']}/actions/workflows",
                    params={"state": state},
                )
                if workflows:
                    yield workflows

    async def create_webhooks_if_not_exists(self) -> None:
        """Create webhooks if they don't exist."""
        if not self.base_url:
            logger.warning(
                "No app host provided, skipping webhook creation. "
                "Without setting up the webhook, the integration will not export live changes from GitHub"
            )
            return

        # Get organizations from integration config
        organizations = ocean.integration_config.get("organizations", [])
        if not organizations:
            logger.warning("No organizations configured, skipping webhook creation")
            return

        # Get repositories for each organization
        async for repos in self.get_repositories(organizations):
            for repo in repos:
                try:
                    # Check existing webhooks
                    webhooks = await self._send_api_request(
                        "GET",
                        f"{self.github_base_url}/repos/{repo['owner']['login']}/{repo['name']}/hooks",
                        headers={"Authorization": f"Bearer {self.token}"},
                    )

                    # Check if webhook already exists
                    webhook_exists = any(
                        hook["config"].get("url") == f"{self.base_url}/webhook"
                        for hook in webhooks
                    )

                    if not webhook_exists:
                        # Create new webhook
                        await self._send_api_request(
                            "POST",
                            f"{self.github_base_url}/repos/{repo['owner']['login']}/{repo['name']}/hooks",
                            json={
                                "name": "web",
                                "active": True,
                                "events": [
                                    "issues",
                                    "pull_request",
                                    "repository",
                                    "team",
                                    "workflow",
                                ],
                                "config": {
                                    "url": f"{self.base_url}/webhook",
                                    "content_type": "json",
                                    "insecure_ssl": "0",
                                },
                            },
                            headers={"Authorization": f"Bearer {self.token}"},
                        )
                        logger.info(
                            f"Created webhook for repository {repo['owner']['login']}/{repo['name']}"
                        )
                    else:
                        logger.info(
                            f"Webhook already exists for repository {repo['owner']['login']}/{repo['name']}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to create webhook for repository {repo['owner']['login']}/{repo['name']}: {str(e)}"
                    )
                    continue

    async def get_single_resource(
        self,
        resource_type: str,
        owner: str,
        repo: str | None,
        identifier: str | int | None,
    ) -> dict[str, Any]:
        """Get a single resource from GitHub API.

        Args:
            resource_type: The type of resource (e.g., 'issues', 'pulls', 'repos', 'teams')
            owner: The owner of the repository or organization
            repo: The repository name (None for organization-level resources)
            identifier: The resource identifier (None for repository-level resources)

        Returns:
            The resource data as a dictionary
        """
        if resource_type == "repos":
            url = f"{self.github_base_url}/repos/{owner}/{repo}"
        elif resource_type == "teams":
            url = f"{self.github_base_url}/orgs/{owner}/teams/{identifier}"
        else:
            url = f"{self.github_base_url}/repos/{owner}/{repo}/{resource_type}/{identifier}"

        return await self._send_api_request("GET", url)
