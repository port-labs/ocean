"""Webhook client for managing Okta event hooks."""

import logging
from typing import List

from okta.clients.event_hooks_client import OktaEventHooksClient

logger = logging.getLogger(__name__)


class OktaWebhookClient(OktaEventHooksClient):
    """Client for managing Okta webhooks and event hooks."""

    def __init__(
        self, okta_domain: str, api_token: str, timeout: int = 30, max_retries: int = 3
    ) -> None:
        """Initialize the webhook client."""
        super().__init__(
            okta_domain=okta_domain,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
        )

    def _get_webhook_name(self) -> str:
        """Get the webhook name for Port Ocean.

        Returns:
            The webhook name
        """
        return "Port Ocean Okta Integration"

    def _get_webhook_url(self, app_host: str) -> str:
        """Get the webhook URL.

        Args:
            app_host: The application host URL

        Returns:
            The webhook URL
        """
        return f"{app_host}/integration/webhook"

    def _get_webhook_events(self) -> List[str]:
        """Get the list of events to subscribe to.

        Returns:
            List of event types
        """
        return [
            # User events
            "user.lifecycle.create",
            "user.lifecycle.activate",
            "user.lifecycle.deactivate",
            "user.lifecycle.suspend",
            "user.lifecycle.unsuspend",
            "user.lifecycle.delete",
            "user.lifecycle.unlock",
            "user.lifecycle.resetPassword",
            "user.lifecycle.expirePassword",
            "user.lifecycle.forgotPassword",
            "user.lifecycle.changePassword",
            "user.lifecycle.changeRecoveryQuestion",
            "user.lifecycle.activate.end",
            "user.lifecycle.deactivate.end",
            "user.lifecycle.suspend.end",
            "user.lifecycle.unsuspend.end",
            "user.lifecycle.delete.end",
            "user.lifecycle.unlock.end",
            "user.lifecycle.resetPassword.end",
            "user.lifecycle.expirePassword.end",
            "user.lifecycle.forgotPassword.end",
            "user.lifecycle.changePassword.end",
            "user.lifecycle.changeRecoveryQuestion.end",
            # Group events
            "group.lifecycle.create",
            "group.lifecycle.update",
            "group.lifecycle.delete",
            "group.user_membership.add",
            "group.user_membership.remove",
            "group.user_membership.add.end",
            "group.user_membership.remove.end",
            # Application events
            "app.lifecycle.create",
            "app.lifecycle.update",
            "app.lifecycle.delete",
            "app.user_membership.add",
            "app.user_membership.remove",
            "app.user_membership.add.end",
            "app.user_membership.remove.end",
        ]

    async def _webhook_exists(self, webhook_url: str) -> bool:
        """Check if a webhook already exists for the given URL.

        Args:
            webhook_url: The webhook URL to check

        Returns:
            True if webhook exists, False otherwise
        """
        try:
            event_hooks = await self.list_event_hooks()
            return any(
                hook.get("channel", {}).get("config", {}).get("uri") == webhook_url
                for hook in event_hooks
            )
        except Exception as e:
            logger.error(f"Error checking for existing webhook: {e}")
            return False

    async def create_webhook_if_not_exists(self, app_host: str) -> None:
        """Create a webhook if one doesn't already exist.

        Args:
            app_host: The application host URL
        """
        webhook_url = self._get_webhook_url(app_host)
        webhook_name = self._get_webhook_name()

        logger.info(f"Setting up Okta event hook for URL: {webhook_url}")

        if await self._webhook_exists(webhook_url):
            logger.info(
                f"Event hook already exists for URL: {webhook_url}, skipping creation."
            )
            return

        try:
            await self.create_event_hook(
                name=webhook_name,
                events=self._get_webhook_events(),
                uri=webhook_url,
                description="Event hook for Port Ocean Okta integration live events",
            )
            logger.info(f"Successfully created event hook for URL: {webhook_url}")
        except Exception as e:
            logger.error(f"Error creating event hook for URL {webhook_url}: {e}")

    async def delete_webhook(self, app_host: str) -> None:
        """Delete the webhook for the given URL.

        Args:
            app_host: The application host URL
        """
        webhook_url = self._get_webhook_url(app_host)

        try:
            event_hooks = await self.list_event_hooks()
            for hook in event_hooks:
                if hook.get("channel", {}).get("config", {}).get("uri") == webhook_url:
                    if hook_id := hook.get("id"):
                        await self.delete_event_hook(hook_id)
                        logger.info(
                            f"Deleted event hook {hook_id} for URL: {webhook_url}"
                        )
                        return

            logger.info(f"No event hook found for URL: {webhook_url}")
        except Exception as e:
            logger.error(f"Error deleting event hook for URL {webhook_url}: {e}")
