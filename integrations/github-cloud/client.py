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
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1

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

    def _parse_organizations(self, organizations_str: str | None) -> list[str]:
        """Parse comma-separated organization string into a list.

        Args:
            organizations_str: Comma-separated string of organization names

        Returns:
            List of organization names
        """
        if not organizations_str:
            return []

        # Split by comma and strip whitespace
        return [org.strip() for org in organizations_str.split(",") if org.strip()]

    async def _check_rate_limit(self, response: httpx.Response) -> None:
        """Check rate limit headers and wait if necessary."""
        remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
        reset_time = int(response.headers.get("X-RateLimit-Reset", 0))

        if remaining <= 1:  # Leave some buffer
            wait_time = max(0, reset_time - int(asyncio.get_event_loop().time()))
            if wait_time > 0:
                logger.warning(
                    f"Rate limit nearly exceeded. Waiting {wait_time} seconds."
                )
                await asyncio.sleep(wait_time)

    async def _handle_rate_limit(
        self, response: httpx.Response, retry_count: int = 0
    ) -> None:
        """Handle rate limit errors with exponential backoff."""
        retry_after = int(
            response.headers.get(
                "Retry-After", self.INITIAL_RETRY_DELAY * (2**retry_count)
            )
        )

        match response.status_code:
            case 403 if "rate limit exceeded" in response.text.lower():
                logger.warning(
                    f"Rate limit exceeded. Waiting {retry_after} seconds before retry {retry_count + 1}/{self.MAX_RETRIES}"
                )
                await asyncio.sleep(retry_after)
            case 429:
                logger.warning(
                    f"Rate limit exceeded. Waiting {retry_after} seconds before retry {retry_count + 1}/{self.MAX_RETRIES}"
                )
                await asyncio.sleep(retry_after)
            case _:
                logger.error(f"Unexpected status code: {response.status_code}")
                raise httpx.HTTPStatusError(
                    f"Unexpected status code: {response.status_code}",
                    request=response.request,
                    response=response,
                )

    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry_count: int = 0,
    ) -> httpx.Response:
        """Send API request with rate limit handling and retries."""
        if headers is None:
            headers = {}
        headers["Authorization"] = f"Bearer {self.token}"

        try:
            async with self.rate_limiter:
                response = await self.client.request(
                    method=method, url=url, params=params, json=json, headers=headers
                )

                # Check rate limits before processing response
                await self._check_rate_limit(response)

                if (
                    response.status_code in (403, 429)
                    and retry_count < self.MAX_RETRIES
                ):
                    await self._handle_rate_limit(response, retry_count)
                    return await self._send_api_request(
                        method=method,
                        url=url,
                        params=params,
                        json=json,
                        headers=headers,
                        retry_count=retry_count + 1,
                    )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 429) and retry_count < self.MAX_RETRIES:
                await self._handle_rate_limit(e.response, retry_count)
                return await self._send_api_request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers,
                    retry_count=retry_count + 1,
                )
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

    async def _to_async_iterator(self, coro):
        """Convert a coroutine into an async iterator that yields a single value."""
        try:
            result = await coro
            if result:
                yield result
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")

    @cache_iterator_result()
    async def get_repositories(
        self, organizations: list[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List repositories."""
        repository_tasks = [
            self._to_async_iterator(
                self._send_api_request(
                    "GET", f"{self.github_base_url}/orgs/{organization}/repos"
                )
            )
            for organization in organizations
        ]
        async for repos in stream_async_iterators_tasks(*repository_tasks):
            yield repos

    async def get_pull_requests(
        self, organizations: list[str], state: str = "all"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List pull requests."""
        pull_request_tasks = []
        async for repos in self.get_repositories(organizations):
            for repo in repos:
                pull_request_tasks.append(
                    self._to_async_iterator(
                        self._send_api_request(
                            "GET",
                            f"{self.github_base_url}/repos/{repo['owner']['login']}/{repo['name']}/pulls",
                            params={
                                "state": state,
                                "sort": "updated",
                                "direction": "desc",
                            },
                        )
                    )
                )

        async for prs in stream_async_iterators_tasks(*pull_request_tasks):
            if prs:
                for pr in prs:
                    if "state" not in pr:
                        pr["state"] = "unknown"
                yield prs

    async def get_issues(
        self, organizations: list[str], state: str = "all"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List issues."""
        issue_tasks = []
        async for repos in self.get_repositories(organizations):
            for repo in repos:
                issue_tasks.append(
                    self._to_async_iterator(
                        self._send_api_request(
                            "GET",
                            f"{self.github_base_url}/repos/{repo['owner']['login']}/{repo['name']}/issues",
                            params={"state": state},
                        )
                    )
                )

        async for issues in stream_async_iterators_tasks(*issue_tasks):
            yield issues

    async def get_teams(
        self, organizations: list[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List teams."""
        team_tasks = [
            self._to_async_iterator(
                self._send_api_request(
                    "GET", f"{self.github_base_url}/orgs/{organization}/teams"
                )
            )
            for organization in organizations
        ]
        async for teams in stream_async_iterators_tasks(*team_tasks):
            yield teams

    async def get_workflows(
        self, organizations: list[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List workflows."""
        workflow_tasks = []
        async for repos in self.get_repositories(organizations):
            for repo in repos:
                workflow_tasks.append(
                    self._to_async_iterator(
                        self._send_api_request(
                            "GET",
                            f"{self.github_base_url}/repos/{repo['owner']['login']}/{repo['name']}/actions/workflows",
                        )
                    )
                )

        async for workflows in stream_async_iterators_tasks(*workflow_tasks):
            yield workflows

    async def get_workflow_runs(
        self, organizations: list[str], workflow_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """List workflow runs."""
        workflow_run_tasks = []
        async for repos in self.get_repositories(organizations):
            for repo in repos:
                workflow_run_tasks.append(
                    self._to_async_iterator(
                        self._send_api_request(
                            "GET",
                            f"{self.github_base_url}/repos/{repo['owner']['login']}/{repo['name']}/actions/workflows/{workflow_id}/runs",
                        )
                    )
                )

        async for workflow_runs in stream_async_iterators_tasks(*workflow_run_tasks):
            yield workflow_runs

    async def create_webhooks_if_not_exists(self) -> None:
        """Create webhooks if they don't exist."""
        if not self.base_url:
            logger.warning(
                "No app host provided, skipping webhook creation. "
                "Without setting up the webhook, the integration will not export live changes from GitHub"
            )
            return

        organizations_str = ocean.integration_config.get("githubOrganization")
        organizations = self._parse_organizations(organizations_str)

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

                    if webhook_exists:
                        logger.info(
                            "Webhook already exists for organization {} (webhook Url: {}), skipping creation.",
                            repo["owner"]["login"],
                            f"{self.base_url}/webhook",
                        )
                        continue

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
                                "workflow_run",
                            ],
                            "config": {
                                "url": f"{self.base_url}/webhook",
                                "content_type": "json",
                            },
                        },
                        headers={"Authorization": f"Bearer {self.token}"},
                    )
                    logger.info(
                        f"Created webhook for repository {repo['owner']['login']}/{repo['name']}"
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
        match resource_type:
            case "repos":
                url = f"{self.github_base_url}/repos/{owner}/{repo}"
                return await self._send_api_request("GET", url)

            case "teams":
                url = f"{self.github_base_url}/orgs/{owner}/teams/{identifier}"
                return await self._send_api_request("GET", url)

            case "workflows":
                url = f"{self.github_base_url}/repos/{owner}/{repo}/actions/workflows"
                workflow = await self._send_api_request("GET", url)
                # Get workflow runs
                runs_url = f"{self.github_base_url}/repos/{owner}/{repo}/actions/workflows/{identifier}/runs"
                runs = await self._send_api_request("GET", runs_url)
                # Add runs to the workflow
                workflow["runs"] = runs.get("workflow_runs", [])
                # Add repository information
                workflow["repository"] = {"name": repo}
                return workflow

            case _:
                url = f"{self.github_base_url}/repos/{owner}/{repo}/{resource_type}/{identifier}"
                return await self._send_api_request("GET", url)
