from loguru import logger
import asyncio
from port_ocean.context.ocean import ocean
from src.github.clients.github import IntegrationClient
from src.github.utils.auth import AuthClient
from src.github.webhook_processor.repository import RepositoryWebhookProcessor


class WebhookClient:
    def __init__(
        self,
        client: "IntegrationClient",
        auth_client: "AuthClient",
    ) -> None:
        self.client = client
        self.auth_client = auth_client
        self.app_host = ocean.app.base_url

    async def setup_webhooks(self) -> None:
        """set up processors and subscribe to webhooks"""

        if self.app_host is None:
            logger.error("app_host not set, skipping webhook setup")
            return

        # repository webhook processor config
        repo_processor = (
            RepositoryWebhookProcessor.create_from_ocean_config_and_integration(
                self.client.base_url, self.auth_client.get_headers()
            )
        )

        async for repos in self.client.get_repositories():
            # tasks to perform for webhook subscriptions
            tasks = []
            for repo in repos:
                task = repo_processor.create_webhook(
                    webhook_url=f"{self.app_host}/integrations/webhook",
                    repo_slug=repo.get("name"),
                    name=repo.get("name"),
                )
                if task is not None:
                    tasks.append(task)

            # subscribe to all webhooks asynchronously
            if tasks:
                await asyncio.gather(*tasks)
