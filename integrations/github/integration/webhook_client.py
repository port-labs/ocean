from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from .github_client import IntegrationClient
from .utils.auth import AuthClient
from .webhook_processor.repository import RepositoryWebhookProcessor


class WebhookClient:
    def __init__(
        self,
        client: "IntegrationClient",
        auth_client: "AuthClient",
    ) -> None:
        self.client = client
        self.auth_client = auth_client
        self.app_host = ocean.config.integration.get("app_host", None)

    async def setup_webhooks(self) -> None:
        """set up processors and subscribe to webhooks"""

        if self.app_host is None:
            logger.error(f"app_host not set, skipping webhook setup")
            return

        # repository webhook processor config
        repo_processor = (
            RepositoryWebhookProcessor.create_from_ocean_config_and_integration(
                self.client.base_url, self.auth_client.get_headers()
            )
        )

        async for repos in self.client.get_repositories():
            # tasks to perform for webhook subscriptions
            tasks = [
                repo_processor.create_webhook(
                    webhook_url=f"{self.app_host}/integrations/webhook",
                    repo_slug=repo.get("name"),
                    name=repo.get("name"),
                )
                for repo in repos
            ]

            # subscribe to all webhooks asynchronously
            async for task in stream_async_iterators_tasks(*tasks):
                await task
