from typing import Any, Dict, List, Optional
from loguru import logger
from httpx import HTTPStatusError
from urllib.parse import quote

from ..models.webhook import WebhookConfig
from github_cloud.types import GithubClientProtocol

class WebhookManager:
    """Manages GitHub webhook operations with improved error handling and validation."""
    
    def __init__(self, client: GithubClientProtocol, config: WebhookConfig):
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