from typing import Any, AsyncGenerator
from bitbucket_cloud.client import BitbucketClient
from loguru import logger
from bitbucket_cloud.webhook_processors.events import (
    RepositoryEvents,
    PullRequestEvents,
)
from httpx import HTTPStatusError


class BitbucketWebhookClient(BitbucketClient):
    """Handles webhook operations for Bitbucket repositories."""

    def __init__(self, *, secret: str | None = None, **kwargs: Any):
        """
        Initialize the BitbucketWebhookClient.

        :param secret: Optional secret for authenticating incoming webhooks.
        :param kwargs: Additional keyword arguments passed to the parent BitbucketClient.
        """
        super().__init__(**kwargs)
        self.secret = secret
        if self.secret:
            logger.info(
                "Received secret for authenticating incoming webhooks. Only authenticated webhooks will be synced."
            )

    @property
    def _workspace_webhook_url(self) -> str:
        """
        Build the workspace webhook URL.

        :return: The URL endpoint for workspace webhook operations.
        """
        return f"{self.base_url}/workspaces/{self.workspace}/hooks"

    async def _webhook_exist(self, webhook_url: str) -> bool:
        """
        Check if a webhook with the specified URL already exists in the workspace.

        :param webhook_url: The URL of the webhook to check.
        :return: True if the webhook exists, False otherwise.
        """
        async for webhook_config_batch in self._send_paginated_api_request(
            self._workspace_webhook_url
        ):
            if any(
                existing_webhook_config.get("url") == webhook_url
                for existing_webhook_config in webhook_config_batch
            ):
                return True
        return False

    async def create_webhook(self, app_host: str) -> None:
        """
        Create a new webhook for the workspace if one doesn't already exist.

        Workspace webhooks are fired for events from all repositories within the workspace.

        :param webhook_url: The URL to which the webhook should send events.
        """
        logger.info("Setting up Bitbucket webhooks for workspace: {}", self.workspace)

        webhook_url = f"{app_host}/integration/webhook"
        if await self._webhook_exist(webhook_url):
            logger.info(
                "Webhook already exists for workspace {} (webhook URL: {}), skipping creation.",
                self.workspace,
                webhook_url,
            )
            return

        webhook_config = {
            "description": "Port Bitbucket Integration",
            "url": webhook_url,
            "active": True,
            "secret": self.secret,
            "events": list(PullRequestEvents + RepositoryEvents),
        }

        try:
            await self._send_api_request(
                self._workspace_webhook_url,
                method="POST",
                json_data=webhook_config,
            )
            logger.info(
                "Successfully created webhook for workspace {} with URL: {}",
                self.workspace,
                webhook_url,
            )
        except HTTPStatusError as http_err:
            logger.error(
                "HTTP error occurred while creating webhook for workspace {} with URL {}: {}",
                self.workspace,
                webhook_url,
                http_err,
            )
        except Exception as err:
            logger.error(
                "Unexpected error occurred while creating webhook for workspace {} with URL {}: {}",
                self.workspace,
                webhook_url,
                err,
            )

    async def retrieve_diff_stat(
        self, repo: str, old_hash: str, new_hash: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve diff statistics between two commits using Bitbucket API
        """
        logger.debug(
            f"Retrieving diff stat for workspace: {self.workspace}, repo: {repo}, old_hash: {old_hash}, new_hash: {new_hash}; retrieve_diff_stat"
        )
        async for diff_stat in self._fetch_paginated_api_with_rate_limiter(
            f"{self.base_url}/repositories/{self.workspace}/{repo}/diffstat/{new_hash}..{old_hash}",
            params={"pagelen": 500},
        ):
            logger.info(
                f"Fetched batch of {len(diff_stat)} diff stat from repository {repo} in workspace {self.workspace}"
            )
            yield diff_stat
