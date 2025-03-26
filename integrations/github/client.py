from typing import Any, AsyncGenerator, Dict, List, Optional
import asyncio
import time

import httpx
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean

# Constants
PAGE_SIZE = 100
MAX_CONCURRENT_REQUESTS = 10

class GitHubRateLimiter:
    """Rate limiter for GitHub API requests."""
    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.rate_limit = {
            "remaining": 5000,
            "reset": time.time() + 3600,
        }

    async def __aenter__(self):
        await self._semaphore.acquire()
        if self.rate_limit["remaining"] <= 1:
            wait_time = self.rate_limit["reset"] - time.time()
            if wait_time > 0:
                logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._semaphore.release()

    def update_rate_limit(self, headers: Dict[str, str]) -> None:
        """Update rate limit information from response headers."""
        self.rate_limit = {
            "remaining": int(headers.get("X-RateLimit-Remaining", 5000)),
            "reset": int(headers.get("X-RateLimit-Reset", time.time() + 3600))
        }

class GitHubClient:
    """Client for interacting with GitHub API v3."""
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, organization: str, webhook_base_url: str | None):
        self.organization = organization
        self.webhook_base_url = webhook_base_url
        self.client = http_async_client
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": ocean.integration_config["github_api_version"]
        }
        self.client.headers.update(self.headers)
        self.rate_limiter = GitHubRateLimiter()

    @classmethod
    def from_ocean_config(cls) -> "GitHubClient":
        """Create a client instance from Ocean configuration."""
        return cls(
            token=ocean.integration_config["token"],
            organization=ocean.integration_config["organization"],
            webhook_base_url=ocean.app.base_url,
        )

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send request to GitHub API with error handling and rate limiting."""
        url = f"{self.BASE_URL}/{endpoint}"
        
        async with self.rate_limiter:
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                )
                response.raise_for_status()
                
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

        while True:
            params["page"] = page
            response = await self._send_api_request(endpoint, method=method, params=params)
            
            if not response:
                break
                
            if isinstance(response, dict) and "items" in response:
                # Some endpoints return paginated results in an 'items' key
                items = response["items"]
            elif isinstance(response, list):
                items = response
            else:
                items = []

            if not items:
                break

            yield items
            page += 1

    @cache_iterator_result()
    async def get_repositories(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all repositories in the organization with pagination."""
        async for repos in self._paginate_request(f"orgs/{self.organization}/repos"):
            logger.info(f"Fetched batch of {len(repos)} repositories from organization {self.organization}")
            yield repos

    async def get_pull_requests(self, repo: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get pull requests for a repository with pagination."""
        params = {"state": "open"}
        async for prs in self._paginate_request(
            f"repos/{self.organization}/{repo}/pulls",
            params=params
        ):
            logger.info(f"Fetched batch of {len(prs)} pull requests from repository {repo}")
            yield prs

    async def get_issues(self, repo: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get issues for a repository with pagination."""
        params = {"state": "open"}
        async for issues in self._paginate_request(
            f"repos/{self.organization}/{repo}/issues",
            params=params
        ):
            logger.info(f"Fetched batch of {len(issues)} issues from repository {repo}")
            yield issues

    async def get_teams(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all teams in the organization with pagination."""
        async for teams in self._paginate_request(f"orgs/{self.organization}/teams"):
            logger.info(f"Fetched batch of {len(teams)} teams from organization {self.organization}")
            yield teams

    async def get_workflows(self, repo: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get workflows for a repository."""
        response = await self._send_api_request(f"repos/{self.organization}/{repo}/actions/workflows")
        if workflows := response.get("workflows", []):
            logger.info(f"Fetched {len(workflows)} workflows from repository {repo}")
            yield workflows

    async def get_workflow_runs(
        self, repo: str, workflow_id: str, per_page: int = 1
    ) -> List[Dict[str, Any]]:
        """Get recent runs for a specific workflow."""
        response = await self._send_api_request(
            f"repos/{self.organization}/{repo}/actions/workflows/{workflow_id}/runs",
            params={"per_page": per_page}
        )
        return response.get("workflow_runs", [])

    async def create_webhooks_if_not_exists(self) -> None:
        """Create webhook for the organization if it doesn't exist."""
        if not self.webhook_base_url:
            logger.warning(
                "No app host provided, skipping webhook creation. "
                "Without webhook setup, the integration won't receive real-time updates from GitHub"
            )
            return

        webhook_url = f"{self.webhook_base_url}/integration/webhook"
        
        # Check existing webhooks
        async for hooks in self._paginate_request(f"orgs/{self.organization}/hooks"):
            for hook in hooks:
                if hook["config"].get("url") == webhook_url:
                    logger.info("Webhook already exists")
                    return

        # Create new webhook with all events
        webhook_data = {
            "name": "web",
            "active": True,
            "events": [
                "repository",
                "pull_request",
                "issues",
                "team",
                "workflow_run"
            ],
            "config": {
                "url": webhook_url,
                "content_type": "json",
            }
        }

        try:
            await self._send_api_request(
                f"orgs/{self.organization}/hooks",
                method="POST",
                json_data=webhook_data
            )
            logger.info("Successfully created webhook")
        except httpx.HTTPError as e:
            logger.error(f"Failed to create webhook: {str(e)}")
