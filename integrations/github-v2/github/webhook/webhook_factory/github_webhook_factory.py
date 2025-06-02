from loguru import logger

from github.clients.github_client import GitHubClient


class GitHubWebhookFactory:
    """Factory for creating and managing GitHub webhooks."""

    def __init__(self, client: GitHubClient, base_url: str):
        self.client = client
        self.base_url = base_url
        self.webhook_url = f"{base_url}/hook"

    async def create_webhooks_for_all_repositories(self) -> None:
        """Create webhooks for all accessible repositories."""
        logger.info("Creating webhooks for all repositories")

        try:
            async for repos_batch in self.client.get_repositories():
                for repo in repos_batch:
                    # Note: This would need proper implementation with actual GitHub API calls
                    # For now, this is a placeholder for the webhook creation logic
                    logger.info(
                        f"Creating webhook for repository {repo['owner']['login']}/{repo['name']}"
                    )
                    logger.debug(f"Webhook URL: {self.webhook_url}")

                    # TODO: Implement actual webhook creation using GitHub API
                    # Example structure:
                    # await self.client.rest.send_api_request(
                    #     "POST",
                    #     f"repos/{repo['owner']['login']}/{repo['name']}/hooks",
                    #     data=webhook_config
                    # )
        except Exception as e:
            logger.error(f"Error creating repository webhooks: {e}")

    async def create_organization_webhooks(self) -> None:
        """Create webhooks for all accessible organizations."""
        logger.info("Creating webhooks for all organizations")

        try:
            async for orgs_batch in self.client.get_organizations():
                for org in orgs_batch:
                    # Note: This would need proper implementation with actual GitHub API calls
                    # For now, this is a placeholder for the webhook creation logic
                    logger.info(f"Creating webhook for organization {org['login']}")
                    logger.debug(f"Webhook URL: {self.webhook_url}")

                    # TODO: Implement actual webhook creation using GitHub API
                    # Example structure:
                    # await self.client.rest.send_api_request(
                    #     "POST",
                    #     f"orgs/{org['login']}/hooks",
                    #     data=webhook_config
                    # )
        except Exception as e:
            logger.error(f"Error creating organization webhooks: {e}")
