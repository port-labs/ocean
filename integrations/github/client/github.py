import asyncio
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Optional, ClassVar
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.context.ocean import ocean
from httpx import Response, HTTPError, HTTPStatusError
from port_ocean.utils.cache import cache_iterator_result

PAGE_SIZE: ClassVar[int] = 100  # GitHub API max items per page

# Set of supported webhook events
SUPPORTED_EVENTS = {
    # Repository events
    "repository", "repository_import", "repository_vulnerability_alert",
    "star", "fork",
    # Team events
    "team", "team_add", "membership",
    # Workflow events
    "workflow_run", "workflow_dispatch", "workflow_job",
    # Issue events
    "issues", "issue_comment",
    # Pull request events
    "pull_request", "pull_request_review", "pull_request_review_comment"
}

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window  # in seconds
        self.requests = []
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        async with self._lock:
            now = datetime.now()
            # Remove expired timestamps
            self.requests = [ts for ts in self.requests 
                           if ts > now - timedelta(seconds=self.time_window)]
            
            if len(self.requests) >= self.max_requests:
                # Calculate sleep time
                sleep_time = (self.requests[0] + 
                            timedelta(seconds=self.time_window) - now).total_seconds()
                if sleep_time > 0:
                    logger.info(f"Rate limit reached. Waiting {sleep_time:.2f} seconds")
                    await asyncio.sleep(sleep_time)
                    # Recursive call after sleep
                    await self.acquire()
                    return
            
            self.requests.append(now)


class GitHubClient:
    def __init__(self, base_url: str, token: str, org: str) -> None:
        self._token = token
        self._base_url = base_url
        self._org = org
        self._client = http_async_client
        self._client.follow_redirects = True
        # Initialize rate limiter (5000 requests per hour per GitHub docs)
        self._rate_limiter = RateLimiter(max_requests=5000, time_window=3600)

    @classmethod
    def from_ocean_configuration(cls) -> "GitHubClient":
        """Create a GitHubClient instance from Ocean configuration.
        
        Returns:
            GitHubClient: A new client instance configured with values from ocean.integration_config
        """
        return cls(
            base_url=ocean.integration_config["github_base_url"],
            token=ocean.integration_config["github_token"],
            org=ocean.integration_config["github_org"]
        )

    def _headers(self) -> dict[str, str]:
        """Get default headers for GitHub API requests.
        
        For fine-grained tokens (github_pat_*), just use the token as is.
        GitHub will handle the authentication format internally.
        """
        return {
            "Authorization": self._token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    async def send_request(
        self,
        method: str,
        url: str,
        data: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
        timeout: int = 30
    ) -> Response | None:
        # Apply rate limiting
        await self._rate_limiter.acquire()
        request_headers = {**(headers or {}), **self._headers()}
        
        try:
            response = await self._client.request(
                method=method,
                url=url,
                data=data,
                params=params,
                headers=request_headers,
                timeout=timeout
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            if response.status_code == 404:
                logger.warning(f"Couldn't access url: {url}. Failed due to 404 error")
                return None
            elif response.status_code == 401:
                logger.error(f"Couldn't access url {url}. Make sure the GitHub token is valid!")
                raise e
            elif response.status_code == 429:
                logger.warning(f"Rate limit hit for url {url}. Consider implementing rate limiting.")
                raise e
            else:
                logger.error(f"Request failed with status code {response.status_code}: {method} to url {url}")
                raise e
        except HTTPError as e:
            logger.error(f"Couldn't send request {method} to url {url}: {str(e)}")
            raise e
        return response

    async def _get_paginated(self, url: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {"per_page": PAGE_SIZE}
        current_url = f"{self._base_url}/{url}"

        while True:
            response = await self.send_request("GET", current_url, params=params)
            if not response:
                break

            data = response.json()
            items: list[dict[str, Any]] = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("items", [])

            if items:
                logger.info(f"Found {len(items)} objects in url {current_url}")
                yield items

            # Handle GitHub Link header pagination
            link_header = response.headers.get("link")
            if not link_header:
                break

            next_url = None
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip()[1:-1]
                    break

            if not next_url:
                break

            current_url = next_url

    @cache_iterator_result()
    async def get_repositories(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for repositories in self._get_paginated(f"orgs/{self._org}/repos"):
            yield repositories

    async def get_issues(self, repo: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for issues in self._get_paginated(f"repos/{self._org}/{repo}/issues"):
            yield issues

    async def get_pull_requests(self, repo: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for pull_requests in self._get_paginated(f"repos/{self._org}/{repo}/pulls"):
            yield pull_requests

    async def get_workflows(self, repo: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for workflows in self._get_paginated(f"repos/{self._org}/{repo}/actions/workflows"):
            yield workflows

    async def get_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for teams in self._get_paginated(f"orgs/{self._org}/teams"):
            yield teams
            
    async def create_webhook(self, repo: str, url: str, secret: str) -> dict[str, Any]:
        """Create a webhook for a repository.
        
        Args:
            repo: Repository name
            url: Webhook callback URL
            secret: Webhook secret for verification
            
        Returns:
            Created webhook details
        """
        data = {
            "name": "web",
            "active": True,
            "events": list(SUPPORTED_EVENTS),
            "config": {
                "url": url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0"
            }
        }
        
        response = await self.send_request(
            "POST", 
            f"{self._base_url}/repos/{self._org}/{repo}/hooks",
            data=data
        )
        if response:
            return response.json()
        return {}
    
    async def get_repository_details(self, repo_name: str) -> dict[str, Any]:
        """Get detailed information about a repository.
        
        Args:
            repo_name: Full repository name (org/repo)
            
        Returns:
            Repository details
        """
        response = await self.send_request("GET", f"{self._base_url}/repos/{repo_name}")
        if response:
            return response.json()
        return {}
        
    async def get_issue_details(self, repo_name: str, issue_number: int) -> dict[str, Any]:
        """Get detailed information about an issue.
        
        Args:
            repo_name: Full repository name (org/repo)
            issue_number: Issue number
            
        Returns:
            Issue details
        """
        response = await self.send_request("GET", f"{self._base_url}/repos/{repo_name}/issues/{issue_number}")
        if response:
            return response.json()
        return {}
        
    async def get_pull_request_details(self, repo_name: str, pr_number: int) -> dict[str, Any]:
        """Get detailed information about a pull request.
        
        Args:
            repo_name: Full repository name (org/repo)
            pr_number: Pull request number
            
        Returns:
            Pull request details including reviews and CI status
        """
        response = await self.send_request("GET", f"{self._base_url}/repos/{repo_name}/pulls/{pr_number}")
        if not response:
            return {}
            
        pr_data = response.json()
        
        # Get review status
        reviews_response = await self.send_request("GET", f"{self._base_url}/repos/{repo_name}/pulls/{pr_number}/reviews")
        if reviews_response:
            pr_data["reviews"] = reviews_response.json()
            
        # Get CI status
        status_response = await self.send_request("GET", f"{self._base_url}/repos/{repo_name}/commits/{pr_data['head']['sha']}/status")
        if status_response:
            pr_data["ci_status"] = status_response.json()
            
        return pr_data