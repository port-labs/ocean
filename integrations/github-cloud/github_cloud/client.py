from typing import AsyncGenerator, Optional, Dict, List
from loguru import logger
from httpx import HTTPStatusError
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from github_cloud.helpers.exceptions import MissingIntegrationCredentialException
from github_cloud.helpers.rate_limiter import GitHubRateLimiter
from github_cloud.models.webhook import WebhookConfig

PAGE_SIZE = 100  # Default page size for paginated requests

class GitHubClient:
    """Client for interacting with the GitHub API."""
    
    def __init__(self, 
                 token: str, 
                 organization: str, 
                 base_url: str = "https://api.github.com"):
        self.token = token
        self.organization = organization
        self.base_url = base_url
        self.rate_limiter = GitHubRateLimiter()

    async def fetch_with_retry(self, url: str, **kwargs) -> Dict:
        """Fetch data from GitHub API with retry logic."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        kwargs["headers"] = headers
        
        try:
            async with self.rate_limiter:
                method = kwargs.pop("method", "GET")
                if method == "GET":
                    response = await http_async_client.get(url, **kwargs)
                elif method == "POST":
                    response = await http_async_client.post(url, **kwargs)
                elif method == "DELETE":
                    response = await http_async_client.delete(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                self.rate_limiter.update_rate_limit(response.headers)
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise

    async def _fetch_paginated_api(self, url: str, **kwargs) -> List[Dict]:
        """Fetch paginated data from GitHub API."""
        results = []
        page = 1
        per_page = 100
        
        while True:
            paginated_url = f"{url}?page={page}&per_page={per_page}"
            response = await self.fetch_with_retry(paginated_url, **kwargs)
            
            if not response:
                break
                
            results.extend(response)
            if len(response) < per_page:
                break
                
            page += 1
            
        return results

    @cache_iterator_result()
    async def get_repositories(self, **kwargs) -> AsyncGenerator[Dict, None]:
        """List repositories."""
        logger.info("Starting to fetch repositories")
        url = f"{self.base_url}/orgs/{self.organization}/repos"
        try:
            results = await self._fetch_paginated_api(url, **kwargs)
            for repo in results:
                logger.debug(f"Yielding repository: {repo['name']}")
                yield repo
            logger.info("Finished fetching repositories")
        except Exception as e:
            logger.error(f"Failed to fetch repositories: {e}")
            raise

    async def get_pull_requests(self, owner: str, repo: str, **kwargs) -> AsyncGenerator[Dict, None]:
        """List pull requests."""
        logger.info(f"Starting to fetch pull requests for {owner}/{repo}")
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        try:
            results = await self._fetch_paginated_api(url, **kwargs)
            for pr in results:
                logger.debug(f"Yielding pull request: {pr['title']}")
                yield pr
            logger.info(f"Finished fetching pull requests for {owner}/{repo}")
        except Exception as e:
            logger.error(f"Failed to fetch pull requests for {owner}/{repo}: {e}")
            raise

    async def get_issues(self, owner: str, repo: str, **kwargs) -> AsyncGenerator[Dict, None]:
        """List issues."""
        logger.info(f"Starting to fetch issues for {owner}/{repo}")
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        try:
            results = await self._fetch_paginated_api(url, **kwargs)
            for issue in results:
                logger.debug(f"Yielding issue: {issue['title']}")
                yield issue
            logger.info(f"Finished fetching issues for {owner}/{repo}")
        except Exception as e:
            logger.error(f"Failed to fetch issues for {owner}/{repo}: {e}")
            raise

    async def get_teams(self, **kwargs) -> AsyncGenerator[Dict, None]:
        """List teams."""
        logger.info("Starting to fetch teams")
        url = f"{self.base_url}/orgs/{self.organization}/teams"
        try:
            results = await self._fetch_paginated_api(url, **kwargs)
            for team in results:
                logger.debug(f"Yielding team: {team['name']}")
                yield team
            logger.info("Finished fetching teams")
        except Exception as e:
            logger.error(f"Failed to fetch teams: {e}")
            raise

    async def get_workflows(self, owner: str, repo: str, **kwargs) -> AsyncGenerator[Dict, None]:
        """List workflows."""
        logger.info(f"Starting to fetch workflows for {owner}/{repo}")
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/workflows"
        try:
            response = await self.fetch_with_retry(url, **kwargs)
            if not response or "workflows" not in response:
                logger.warning(f"No workflows found for {owner}/{repo}")
                return
            
            for workflow in response["workflows"]:
                if "name" in workflow:
                    logger.debug(f"Yielding workflow: {workflow['name']}")
                    yield workflow
                else:
                    logger.warning(f"Unexpected workflow structure: {workflow}")
            logger.info(f"Finished fetching workflows for {owner}/{repo}")
        except Exception as e:
            logger.error(f"Failed to fetch workflows for {owner}/{repo}: {e}")
            raise

    # Webhook methods
    async def get_repository_webhooks(self, owner: str, repo: str) -> List[Dict]:
        """Get all webhooks for a repository."""
        url = f"{self.base_url}/repos/{owner}/{repo}/hooks"
        try:
            return await self._fetch_paginated_api(url)
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Repository {owner}/{repo} not found or not accessible")
                return []
            raise

    async def create_webhook(self, owner: str, repo: str, webhook_config: WebhookConfig) -> Optional[Dict]:
        """Create a new webhook for a repository."""
        webhook_data = {
            "name": "web",
            "active": True,
            "events": [event.value for event in webhook_config.events],
            "config": {
                "url": webhook_config.url,
                "content_type": webhook_config.content_type,
                "secret": webhook_config.secret,
                "insecure_ssl": webhook_config.insecure_ssl,
            },
        }

        url = f"{self.base_url}/repos/{owner}/{repo}/hooks"
        try:
            return await self.fetch_with_retry(url, json=webhook_data, method="POST")
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Repository {owner}/{repo} not found or not accessible")
                return None
            raise

    async def delete_webhook(self, owner: str, repo: str, hook_id: int) -> bool:
        """Delete a webhook from a repository."""
        url = f"{self.base_url}/repos/{owner}/{repo}/hooks/{hook_id}"
        try:
            await self.fetch_with_retry(url, method="DELETE")
            return True
        except Exception as e:
            logger.error(f"Failed to delete webhook {hook_id} from {owner}/{repo}: {e}")
            return False


class WebhookManager:
    """Manages GitHub webhook operations."""
    
    def __init__(self, client: GitHubClient, config: WebhookConfig):
        self.client = client
        self.config = config

    async def sync_repository_webhooks(self, owner: str, repo: str) -> bool:
        """Synchronize webhooks for a repository."""
        try:
            # Get existing webhooks
            webhooks = await self.client.get_repository_webhooks(owner, repo)
            
            # Find webhooks with matching URL
            matching_webhooks = [
                webhook for webhook in webhooks
                if webhook.get("config", {}).get("url") == self.config.url
            ]

            # Delete duplicate webhooks
            for webhook in matching_webhooks[1:]:
                await self.client.delete_webhook(owner, repo, webhook["id"])

            if not matching_webhooks:
                # Create new webhook if none exists
                return await self.client.create_webhook(owner, repo, self.config) is not None

            return True
        except Exception as e:
            logger.error(f"Failed to sync webhooks for {owner}/{repo}: {e}")
            return False