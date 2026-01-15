from clients.sentry import SentryClient
from typing import Any
from clients.exceptions import ResourceNotFoundError
from loguru import logger


class SentryWebhookClient(SentryClient):
    """Handles Sentry Event Hooks operations."""

    async def _get_sentry_apps(self) -> list[dict[str, Any]]:
        """List sentry apps for the organization."""
        url = f"organizations/{self.organization}/sentry-apps/"
        try:
            response = await self.send_api_request("GET", url)
            return response.json()
        except ResourceNotFoundError:
            return []

    async def ensure_sentry_apps(self, base_url: str) -> None:
        """Ensure sentry apps exist for the organization."""

        logger.info("Ensuring Sentry apps exist for the organization")
        webhook_url = f"{base_url.rstrip('/')}/integration/webhook"

        apps = await self._get_sentry_apps()
        logger.debug(f"Found {len(apps)} Sentry apps for the organization")
        if not any(app.get("webhookUrl") == webhook_url for app in apps):
            logger.warning(
                f"Sentry app with webhook URL {webhook_url} does not exist. Skipping webhook creation..."
            )
