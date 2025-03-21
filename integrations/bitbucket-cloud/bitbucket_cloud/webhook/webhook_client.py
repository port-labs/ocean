from typing import Any
import json

from bitbucket_cloud.client import BitbucketClient
from loguru import logger
from bitbucket_cloud.webhook.events import (
    RepositoryEvents,
    PullRequestEvents,
    PushEvents,
)
from httpx import HTTPStatusError
import hashlib
import hmac

from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)


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

    async def authenticate_incoming_webhook(
        self, payload: EventPayload, headers: EventHeaders
    ) -> bool:
        """Authenticate the Bitbucket webhook payload using the secret.
        Skip if secret was not provided
        """
        if not self.secret:
            logger.warning(
                "No secret provided for authenticating incoming webhooks, skipping authentication."
            )
            return True

        signature = headers.get("x-hub-signature")

        if not signature:
            logger.error(
                "Aborting webhook authentication due to missing X-Hub-Signature header"
            )
            return False

        payload_bytes = json.dumps(payload).encode()
        hash_object = hmac.new(self.secret.encode(), payload_bytes, hashlib.sha256)
        expected_signature = "sha256=" + hash_object.hexdigest()

        return hmac.compare_digest(signature, expected_signature)

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
            webhook_url = f"{webhook_url}/integration/webhook"
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
            "events": list(PullRequestEvents + RepositoryEvents + PushEvents),
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
