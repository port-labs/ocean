from typing import Any, Dict, List
from loguru import logger
from github.clients.http.rest_client import GithubRestClient

PAGE_SIZE = 100


class GithubWebhookClient(GithubRestClient):
    def __init__(self, *, webhook_secret: str | None = None, **kwargs: Any):
        """
        Initialize the GitHub Webhook Client.

        :param webhook_secret: Optional secret for authenticating incoming webhooks.
        :param kwargs: Additional keyword arguments passed to the parent GitHub Rest Client.
        """
        GithubRestClient.__init__(self, **kwargs)
        self.webhook_secret = webhook_secret
        if self.webhook_secret:
            logger.info(
                "Received secret for authenticating incoming webhooks. Only authenticated webhooks will be synced."
            )

    async def _get_existing_webhook(self, webhook_url: str) -> Dict[str, Any] | None:
        """Return the existing webhook matching the given URL, or None if not found."""
        async for hooks in self.send_paginated_request(
            f"{self.base_url}/orgs/{self.organization}/hooks"
        ):
            existing_webhook = next(
                (hook for hook in hooks if hook["config"]["url"] == webhook_url),
                None,
            )
            if existing_webhook:
                return existing_webhook
        return None

    async def _patch_webhook(
        self, webhook_id: str, config_data: dict[str, str]
    ) -> None:
        webhook_data = {"config": config_data}

        logger.info(f"Patching webhook {webhook_id} to modify config data")
        await self.send_api_request(
            f"{self.base_url}/orgs/{self.organization}/hooks/{webhook_id}",
            method="PATCH",
            json_data=webhook_data,
        )
        logger.info(f"Successfully patched webhook {webhook_id} with secret")

    def _build_webhook_config(self, webhook_url: str) -> dict[str, str]:
        config = {
            "url": webhook_url,
            "content_type": "json",
        }
        if self.webhook_secret:
            config["secret"] = self.webhook_secret
        return config

    async def upsert_webhook(self, base_url: str, webhook_events: List[str]) -> None:
        """Create or update GitHub organization webhook with secret handling."""

        webhook_url = f"{base_url}/integration/webhook"

        existing_webhook = await self._get_existing_webhook(webhook_url)

        # Create new webhook with events
        if not existing_webhook:
            logger.info("Creating new GitHub webhook")
            webhook_data = {
                "name": "web",
                "active": True,
                "events": webhook_events,
                "config": self._build_webhook_config(webhook_url),
            }

            await self.send_api_request(
                f"{self.base_url}/orgs/{self.organization}/hooks",
                method="POST",
                json_data=webhook_data,
            )
            logger.info("Successfully created webhook")
            return

        existing_webhook_id = existing_webhook["id"]
        existing_webhook_secret = existing_webhook["config"].get("secret")

        logger.info(f"Found existing webhook with ID: {existing_webhook_id}")

        # Check if patching is necessary
        if bool(self.webhook_secret) ^ bool(existing_webhook_secret):
            logger.info(f"Patching webhook {existing_webhook_id} to update secret")

            config_data = self._build_webhook_config(webhook_url)

            await self._patch_webhook(existing_webhook_id, config_data)
            return

        logger.info("Webhook already exists with appropriate configuration")
