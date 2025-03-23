from typing import Dict, Any, List
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

    async def get_repositories(self) -> List[Dict[str, Any]]:
        """Get all repositories for the organization"""
        return await self._make_request("GET", f"orgs/{self.org}/repos")

    async def get_repository(self, repo: str) -> Dict[str, Any]:
        """Get a specific repository"""
        return await self._make_request("GET", f"repos/{self.org}/{repo}")

    async def get_pull_requests(self, repo: str, state: str = "all") -> List[Dict[str, Any]]:
        """Get pull requests for a repository"""
        return await self._make_request("GET", f"repos/{self.org}/{repo}/pulls", params={"state": state})

    async def get_issues(self, repo: str, state: str = "all") -> List[Dict[str, Any]]:
        """Get issues for a repository"""
        return await self._make_request("GET", f"repos/{self.org}/{repo}/issues", params={"state": state})

    async def get_teams(self) -> List[Dict[str, Any]]:
        """Get all teams in the organization"""
        return await self._make_request("GET", f"orgs/{self.org}/teams")

    async def get_workflows(self, repo: str) -> List[Dict[str, Any]]:
        """Get GitHub Actions workflows for a repository"""
        return await self._make_request("GET", f"repos/{self.org}/{repo}/actions/workflows")

    async def get_workflow_runs(self, repo: str, workflow_id: str) -> List[Dict[str, Any]]:
        """Get workflow runs for a specific workflow"""
        return await self._make_request("GET", f"repos/{self.org}/{repo}/actions/workflows/{workflow_id}/runs")
