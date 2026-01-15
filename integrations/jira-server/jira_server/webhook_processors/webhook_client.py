from typing import Any
from loguru import logger
from jira_server.client import JiraServerClient
from jira_server.webhook_processors.events import (
    JiraIssueEvents,
    JiraProjectEvents,
    JiraUserEvents,
)
from httpx import HTTPStatusError


class JiraWebhookClient(JiraServerClient):
    """
    Client for interacting with Jira Server webhooks.
    """

    def __init__(self, *, secret: str | None = None, **kwargs: Any) -> None:
        """
        Initialize the JiraWebhookClient.
        """
        super().__init__(**kwargs)
        self.secret = secret
        self.webhook_api_url = f"{self.api_url.rstrip("/")}/rest/webhooks/1.0"

    async def _webhook_exist(self, webhook_url: str) -> bool:
        """
        Check if a webhook with the specified URL already exists.
        """
        try:
            webhooks = await self._send_api_request(
                "GET", f"{self.webhook_api_url}/webhook"
            )

            for webhook in webhooks:
                if webhook.get("url") == webhook_url:
                    return True
            return False
        except HTTPStatusError as e:
            logger.warning(f"Failed to check if webhook exists: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking webhook existence: {e}")
            return False

    async def create_webhook(self, app_host: str) -> None:
        """
        Create a new webhook for Jira Server if it doesn't already exist.
        """
        webhook_url = f"{app_host}/integration/webhook"

        if await self._webhook_exist(webhook_url):
            logger.info(
                f"Webhook already exists for URL: {webhook_url}, skipping creation."
            )
            return

        webhook_config = {
            "name": "Port Ocean Jira Integration",
            "url": webhook_url,
            "events": JiraIssueEvents + JiraProjectEvents + JiraUserEvents,
            "configuration": {"EXCLUDE_BODY": "false"},
            "active": "true",
            "excludeBody": False,  # for backward compatibility with 9.x
        }

        try:
            await self._send_api_request(
                "POST", f"{self.webhook_api_url}/webhook", json=webhook_config
            )
            logger.info(f"Successfully created webhook with URL: {webhook_url}")
        except HTTPStatusError as e:
            logger.error(f"HTTP error occurred while creating webhook: {e}")
        except Exception as e:
            logger.error(f"Unexpected error occurred while creating webhook: {e}")
