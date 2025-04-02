from typing import Any, AsyncGenerator, Optional, Dict, List, TypeVar
import asyncio
from loguru import logger
from httpx import HTTPStatusError
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from github_cloud.helpers.exceptions import MissingIntegrationCredentialException
from github_cloud.helpers.rate_limiter import GitHubRateLimiter
from urllib.parse import quote
from dataclasses import dataclass
from enum import Enum
from github_cloud.models.webhook import WebhookConfig, WebhookEvent

PAGE_SIZE = 100  # Default page size for paginated requests

T = TypeVar('T')

class ResourceType(Enum):
    """Enumeration of supported GitHub resource types."""
    REPOSITORY = "repository"
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"
    TEAM = "team"
    WORKFLOW = "workflow"
    USER = "user"
    ORGANIZATION = "organization"
    BRANCH = "branch"
    COMMIT = "commit"

@dataclass
class ResourceEndpoint:
    """Configuration for a GitHub API endpoint."""
    path_template: str
    requires_organization: bool = True
    supports_pagination: bool = False
    response_type: str = "single"  # "single" or "list"

class WebhookEvent(Enum):
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    ISSUES = "issues"
    WORKFLOW_RUN = "workflow_run"

@dataclass
class WebhookConfig:
    url: str
    secret: str
    events: List[WebhookEvent]
    content_type: str = "json"
    insecure_ssl: str = "0"

class WebhookManager:
    """Manages GitHub webhook operations with improved error handling and validation."""
    
    def __init__(self, client: "GithubClient", config: WebhookConfig):
        self.client = client
        self.config = config
        self.base_url = client.base_url

    async def validate_webhook_url(self) -> bool:
        """Validate that the webhook URL is accessible."""
        try:
            response = await self.client.client.head(self.config.url)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Webhook URL validation failed: {e}")
            return False

    async def get_repository_webhooks(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Get all webhooks for a repository."""
        url = f"{self.base_url}/repos/{owner}/{quote(repo)}/hooks"
        webhooks = []
        try:
            async for page in self.client._fetch_paginated_api(url):
                webhooks.extend(page)
        except Exception as e:
            logger.error(f"Failed to fetch webhooks for {owner}/{repo}: {e}")
        return webhooks

    async def create_webhook(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Create a new webhook for a repository."""
        webhook_data = {
            "name": "web",
            "active": True,
            "events": [event.value for event in self.config.events],
            "config": {
                "url": self.config.url,
                "content_type": self.config.content_type,
                "secret": self.config.secret,
                "insecure_ssl": self.config.insecure_ssl,
            },
        }

        url = f"{self.base_url}/repos/{owner}/{quote(repo)}/hooks"
        try:
            return await self.client.fetch_with_retry(url, method="POST", json_data=webhook_data)
        except HTTPStatusError as e:
            if e.response.status_code == 422:
                logger.error(f"Invalid webhook configuration for {owner}/{repo}: {e.response.text}")
            elif e.response.status_code == 404:
                logger.error(f"Repository not found: {owner}/{repo}")
            else:
                logger.error(f"Failed to create webhook for {owner}/{repo}: {e}")
            return None

    async def delete_webhook(self, owner: str, repo: str, hook_id: int) -> bool:
        """Delete a webhook from a repository."""
        url = f"{self.base_url}/repos/{owner}/{quote(repo)}/hooks/{hook_id}"
        try:
            await self.client.fetch_with_retry(url, method="DELETE")
            return True
        except Exception as e:
            logger.error(f"Failed to delete webhook {hook_id} from {owner}/{repo}: {e}")
            return False

    async def sync_repository_webhooks(self, owner: str, repo: str) -> bool:
        """Synchronize webhooks for a repository, ensuring only one webhook exists with the correct configuration."""
        try:
            # Get existing webhooks
            webhooks = await self.get_repository_webhooks(owner, repo)
            
            # Find webhooks with matching URL
            matching_webhooks = [
                webhook for webhook in webhooks
                if webhook.get("config", {}).get("url") == self.config.url
            ]

            # Delete duplicate webhooks
            for webhook in matching_webhooks[1:]:
                await self.delete_webhook(owner, repo, webhook["id"])

            if not matching_webhooks:
                # Create new webhook if none exists
                return await self.create_webhook(owner, repo) is not None

            return True
        except Exception as e:
            logger.error(f"Failed to sync webhooks for {owner}/{repo}: {e}")
            return False

    async def setup_webhooks_for_all_repositories(self) -> Dict[str, List[str]]:
        """Set up webhooks for all repositories and return a summary of successes and failures."""
        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }

        # Validate webhook URL first
        if not await self.validate_webhook_url():
            logger.error("Webhook URL validation failed. Aborting webhook setup.")
            return results

        try:
            async for repo in self.client.get_repositories():
                owner = repo["owner"]["login"]
                repo_name = repo["name"]
                repo_full_name = f"{owner}/{repo_name}"

                try:
                    success = await self.sync_repository_webhooks(owner, repo_name)
                    if success:
                        results["success"].append(repo_full_name)
                    else:
                        results["failed"].append(repo_full_name)
                except Exception as e:
                    logger.error(f"Error processing webhooks for {repo_full_name}: {e}")
                    results["failed"].append(repo_full_name)

        except Exception as e:
            logger.error(f"Failed to process repositories for webhook setup: {e}")

        return results

class GithubClient:
    """Client for interacting with the GitHub API."""

    def __init__(
        self,
        base_url: str,
        app_host: str,
        token: Optional[str] = None,
        secret: Optional[str] = None,
        organization: Optional[str] = None,
    ) -> None:
        self.base_url = base_url
        self.app_host = app_host
        self.client = http_async_client
        self.rate_limiter = GitHubRateLimiter()
        self.secret = secret
        self.organization = organization

        if token:
            self.headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            }
        else:
            raise MissingIntegrationCredentialException("Access token must be provided")
        self.client.headers.update(self.headers)

        # Initialize managers
        from github_cloud.managers.resource_manager import ResourceManager
        from github_cloud.managers.webhook_manager import WebhookManager
        
        self.resource_manager = ResourceManager(self)
        if secret:
            webhook_config = WebhookConfig(
                url=f"{app_host}/integration/webhook",
                secret=secret,
                events=[
                    WebhookEvent.PUSH,
                    WebhookEvent.PULL_REQUEST,
                    WebhookEvent.ISSUES,
                    WebhookEvent.WORKFLOW_RUN
                ]
            )
            self.webhook_manager = WebhookManager(self, webhook_config)

    @classmethod
    def create_from_ocean_config(cls) -> "GithubClient":
        return cls(
            token=ocean.integration_config["github_access_token"],
            base_url=ocean.integration_config["github_base_url"],
            app_host=ocean.integration_config["app_host"],
            secret=ocean.integration_config.get("webhook_secret"),
            organization=ocean.integration_config.get("github_organization"),
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

    async def setup_repository_webhooks(self) -> Dict[str, List[str]]:
        """Set up webhooks for all repositories using the WebhookManager."""
        if not hasattr(self, 'webhook_manager'):
            logger.error("Webhook manager not initialized. Secret is required for webhook operations.")
            return {"success": [], "failed": [], "skipped": []}
        
        return await self.webhook_manager.setup_webhooks_for_all_repositories()

    async def fetch_resource(self, resource_type: str, identifier: str, **kwargs) -> Dict[str, Any]:
        """
        Fetch a single resource from GitHub API using the ResourceManager.
        
        Args:
            resource_type: Type of resource to fetch
            identifier: Primary identifier for the resource
            **kwargs: Additional parameters needed for specific resource types
            
        Returns:
            Dict containing the resource data
        """
        return await self.resource_manager.get_resource_with_retry(resource_type, identifier, **kwargs)

    async def get_resource_by_url(self, url: str) -> dict[str, Any]:
        """Get a resource by URL."""
        try:
            response = await self.fetch_with_retry(url)
            return response
        except Exception as e:
            logger.error(f"Error fetching resource by URL {url}: {e}")
            raise e