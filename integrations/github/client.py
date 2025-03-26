from typing import AsyncGenerator, Dict, Any, List
from ocean.port_ocean.context import ocean
from port_ocean.clients.port.client import PortClient

from port_ocean.context.ocean import logger
import asyncio
import time

class GitHubClient:
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: str, org: str):
        self.client = PortClient()
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        self.org = org
        self.rate_limit = {
            "remaining": 5000,
            "reset": time.time() + 3600
        }

    @classmethod
    def create_from_ocean_config(cls) -> "GitHubClient":
        """Create a client instance from Ocean configuration."""
        return cls(
            token=ocean.integration_config.get_secret("github_token"),
            org=ocean.integration_config.get("organization")
        )

    async def _handle_rate_limit(self) -> None:
        """Handle GitHub API rate limiting"""
        if self.rate_limit["remaining"] <= 1:
            wait_time = self.rate_limit["reset"] - time.time()
            if wait_time > 0:
                logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make a rate-limited request to GitHub API"""
        await self._handle_rate_limit()
        url = f"{self.BASE_URL}/{endpoint}"
        
        # Add default pagination parameters if not provided
        if "params" not in kwargs:
            kwargs["params"] = {}
        if "per_page" not in kwargs["params"]:
            kwargs["params"]["per_page"] = 100  # GitHub's max items per page
        
        try:
            response = await self.client.request(
                method=method,
                url=url,
                headers=self.headers,
                **kwargs
            )
            
            # Update rate limit info
            self.rate_limit = {
                "remaining": int(response.headers.get("X-RateLimit-Remaining", 5000)),
                "reset": int(response.headers.get("X-RateLimit-Reset", time.time() + 3600))
            }
            
            response.raise_for_status()
            return response.json() if response.text else None
            
        except Exception as e:
            logger.error(f"GitHub API request failed: {str(e)}")
            raise

    async def get_repositories(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get repositories with pagination."""
        page = 1
        while True:
            repos = await self._make_request(
                "GET",
                f"orgs/{self.org}/repos",
                params={"page": page, "per_page": 100}
            )
            if not repos:
                break
            yield repos
            page += 1

    async def get_pull_requests(self, repo: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get pull requests with pagination."""
        page = 1
        while True:
            prs = await self._make_request(
                "GET",
                f"repos/{self.org}/{repo}/pulls",
                params={"page": page, "per_page": 100, "state": "all"}
            )
            if not prs:
                break
            yield prs
            page += 1

    async def get_issues(self, repo: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get issues with pagination."""
        page = 1
        while True:
            issues = await self._make_request(
                "GET",
                f"repos/{self.org}/{repo}/issues",
                params={"page": page, "per_page": 100, "state": "all"}
            )
            if not issues:
                break
            yield issues
            page += 1

    async def get_teams(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get teams with pagination."""
        page = 1
        while True:
            teams = await self._make_request(
                "GET",
                f"orgs/{self.org}/teams",
                params={"page": page, "per_page": 100}
            )
            if not teams:
                break
            yield teams
            page += 1

    async def get_workflows(self, repo: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get workflows with pagination."""
        workflows = await self._make_request(
            "GET",
            f"repos/{self.org}/{repo}/actions/workflows"
        )
        if workflows:
            yield workflows.get("workflows", [])

    async def get_repository(self, repo: str) -> Dict[str, Any]:
        """Get a specific repository"""
        return await self._make_request("GET", f"repos/{self.org}/{repo}")

    async def get_workflow_runs(self, repo: str, workflow_id: str) -> List[Dict[str, Any]]:
        """Get workflow runs for a specific workflow"""
        return await self._make_request("GET", f"repos/{self.org}/{repo}/actions/workflows/{workflow_id}/runs")
