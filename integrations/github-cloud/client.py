from typing import Any, AsyncGenerator, Optional
import asyncio
from loguru import logger
from httpx import HTTPStatusError
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from github_cloud.helpers.exceptions import MissingIntegrationCredentialException
from github_cloud.helpers.rate_limiter import GitHubRateLimiter
from urllib.parse import quote

PAGE_SIZE = 100  # Default page size for paginated requests


class GithubClient:
    """Client for interacting with the GitHub API."""

    def __init__(
        self,
        base_url: str,
        app_host: str,
        token: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> None:
        self.base_url = base_url
        self.app_host = app_host
        self.client = http_async_client
        self.rate_limiter = GitHubRateLimiter()
        self.secret = secret

        if token:
            self.headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            }
        else:
            raise MissingIntegrationCredentialException("Access token must be provided")
        self.client.headers.update(self.headers)

    @classmethod
    def create_from_ocean_config(cls) -> "GithubClient":
        return cls(
            token=ocean.integration_config["github_access_token"],
            base_url=ocean.integration_config["github_base_url"],
            app_host=ocean.integration_config["app_host"],
            secret=ocean.integration_config.get("webhook_secret"),
        )

    async def fetch_with_retry(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
        retries: int = 3,
    ) -> Any:
        """Fetch data with retry logic for handling rate limits."""
        for attempt in range(retries):
            try:
                async with self.rate_limiter:
                    response = await self.client.request(
                        method=method, url=url, headers=self.headers, params=params, json=json_data
                    )
                    match response.status_code:
                        case 200:
                            # Check if response.json is awaitable
                            if asyncio.iscoroutinefunction(response.json):
                                return await response.json()
                            else:
                                return response.json()
                        case 429:  # Rate limit exceeded
                            retry_after = int(response.headers.get("Retry-After", 1))
                            logger.warning(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
                            await asyncio.sleep(retry_after)
                            self.rate_limiter.update_rate_limit(response.headers)
                        case _:
                            response.raise_for_status()
            except Exception as e:
                logger.error(f"Error during fetch attempt {attempt + 1} for URL {url}: {e}")
        raise Exception(f"Max retries exceeded for URL {url}")

    async def _fetch_paginated_api(
        self, url: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated data from the GitHub API."""
        page = 1
        params = params or {}
        params.update({"per_page": PAGE_SIZE})

        while True:
            params["page"] = page
            try:
                data = await self.fetch_with_retry(url, params=params)
                if not data:
                    break
                yield data
                page += 1
            except Exception as e:
                logger.error(f"Error fetching paginated data from {url}: {e}")
                break

    @cache_iterator_result()
    async def get_repositories(self, params: Optional[dict[str, Any]] = None) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch all repositories for the authenticated user."""
        url = f"{self.base_url}/user/repos"
        try:
            async for repos in self._fetch_paginated_api(url, params=params):
                for repo in repos:
                    yield repo
        except Exception as e:
            logger.error(f"Error fetching repositories: {e}")

    async def get_issues(self, username: str, repo: str) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch all issues for a specific repository."""
        url = f"{self.base_url}/repos/{username}/{repo}/issues"
        try:
            async for issues in self._fetch_paginated_api(url):
                for issue in issues:
                    yield issue
        except Exception as e:
            logger.error(f"Error fetching issues for {username}/{repo}: {e}")

    async def get_pull_requests(self, username: str, repo: str) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch all pull requests for a specific repository."""
        url = f"{self.base_url}/repos/{username}/{repo}/pulls"
        try:
            async for pull_requests in self._fetch_paginated_api(url):
                for pull_request in pull_requests:
                    yield pull_request
        except Exception as e:
            logger.error(f"Error fetching pull requests for {username}/{repo}: {e}")

    async def get_organizations(self) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch all organizations the authenticated user belongs to."""
        url = f"{self.base_url}/user/orgs"
        try:
            async for orgs in self._fetch_paginated_api(url):
                for org in orgs:
                    yield org
        except Exception as e:
            logger.error(f"Error fetching organizations: {e}")

    async def get_teams(self, org: str) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch all teams for a specific organization."""
        url = f"{self.base_url}/orgs/{org}/teams"
        try:
            async for teams in self._fetch_paginated_api(url):
                for team in teams:
                    yield team
        except Exception as e:
            logger.error(f"Error fetching teams for organization {org}: {e}")

    async def get_workflows(self, username: str, repo: str) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch all workflows for a specific repository."""
        url = f"{self.base_url}/repos/{username}/{repo}/actions/workflows"
        try:
            async for workflows in self._fetch_paginated_api(url):
                for workflow in workflows:
                    yield workflow
        except Exception as e:
            logger.error(f"Error fetching workflows for {username}/{repo}: {e}")

    async def _webhook_exists(self, owner: str, repo: str, webhook_url: str) -> bool:
        """Check if a webhook with the specified URL already exists in the repository."""
        url = f"{self.base_url}/repos/{owner}/{quote(repo)}/hooks"
        try:
            async for webhooks in self._fetch_paginated_api(url):
                if any(
                    webhook.get("config", {}).get("url") == webhook_url
                    for webhook in webhooks
                ):
                    return True
        except Exception as e:
            logger.error(f"Error checking webhook existence for {owner}/{repo}: {e}")
        return False

    async def create_webhooks_if_not_exists(self, app_host: str) -> None:
        """Create webhooks for all repositories if they don't already exist."""
        webhook_url = f"{app_host}/integration/webhook"
        try:
            async for repo in self.get_repositories():
                owner = repo["owner"]["login"]
                repo_name = repo["name"]

                try:
                    if await self._webhook_exists(owner, repo_name, webhook_url):
                        logger.info(f"Webhook already exists for {owner}/{repo_name}. Skipping.")
                        continue

                    webhook_config = {
                        "name": "web",
                        "active": True,
                        "events": ["push", "pull_request", "issues", "workflow_run"],
                        "config": {
                            "url": webhook_url,
                            "content_type": "json",
                            "secret": self.secret,
                            "insecure_ssl": "0",  # Set to "1" if testing with self-signed certificates
                        },
                    }

                    url = f"{self.base_url}/repos/{owner}/{quote(repo_name)}/hooks"
                    await self.fetch_with_retry(url, method="POST", json_data=webhook_config)
                    logger.info(f"Webhook created for {owner}/{repo_name}.")
                except HTTPStatusError as e:
                    if e.response.status_code == 404:
                        logger.error(f"Repository not found: {owner}/{repo_name}. Skipping.")
                    elif e.response.status_code == 422:
                        logger.error(
                            f"Failed to create webhook for {owner}/{repo_name}: {e.response.text}"
                        )
                    else:
                        logger.error(
                            f"HTTP error occurred while creating webhook for {owner}/{repo_name}: {e}"
                        )
                except Exception as e:
                    logger.error(f"Unexpected error occurred while creating webhook for {owner}/{repo_name}: {e}")
        except Exception as e:
            logger.error(f"Failed to set up webhooks: {e}")


    async def get_single_resource(self, object_type: str, identifier: str) -> dict[str, Any]:
            """Fetch a single resource from GitHub API."""

            endpoints = {
                "repository": f"repos/{self.organization}/{identifier}",
                "pull-request": f"repos/{self.organization}/{identifier}/pulls",
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

    async def get_resource_by_url(self, url: str) -> dict[str, Any]:
        """Get a resource by URL."""
        try:
            response = await self.fetch_with_retry(url)
            return response
        except Exception as e:
            logger.error(f"Error fetching resource by URL {url}: {e}")
            raise e