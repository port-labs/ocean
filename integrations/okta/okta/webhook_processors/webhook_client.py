from typing import Any, AsyncGenerator, Dict, List

from httpx import HTTPStatusError
from loguru import logger

from okta.clients.http.client import OktaClient
from port_ocean.context.ocean import ocean
from okta.utils import default_event_subscriptions


class OktaWebhookClient(OktaClient):
    """Handles Okta Event Hooks operations."""

    async def list_event_hooks(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        async for page in self.send_paginated_request("/eventHooks"):
            yield page

    async def _event_hook_exists(self, webhook_url: str) -> bool:
        async for hooks in self.list_event_hooks():
            if any(
                hook.get("channel", {}).get("config", {}).get("uri") == webhook_url
                for hook in hooks
            ):
                return True
        return False

    async def ensure_event_hook(self, app_host: str) -> None:
        """Create an event hook if missing, subscribing to relevant events."""
        logger.info("Ensuring Okta Event Hook exists")

        app_host = app_host.strip("/")
        webhook_url = f"{app_host}/integration/webhook"
        if await self._event_hook_exists(webhook_url):
            logger.info("Event Hook already exists; skipping creation")
            return

        subscribed_events = default_event_subscriptions()

        config_dict: Dict[str, Any] = {
            "uri": webhook_url,
            "headers": [],
        }

        if secret := ocean.integration_config.get("webhook_secret"):
            config_dict["authScheme"] = {
                "type": "HEADER",
                "key": "Authorization",
                "value": secret,
            }

        channel_config = {
            "type": "HTTP",
            "version": "1.0.0",
            "config": config_dict,
        }

        body = {
            "name": "Port Okta Event Hook",
            "events": {"type": "EVENT_TYPE", "items": subscribed_events},
            "channel": channel_config,
            "description": "Event hook for Port Okta integration",
        }

        try:
            resp = await self.make_request("/eventHooks", method="POST", json_data=body)
            logger.info("Successfully created Okta Event Hook")

            # Immediately verify using the verify link if provided
            links = resp.json().get("_links", {})
            verify = links.get("verify", {})
            if href := verify.get("href"):
                try:
                    await self.make_request(
                        href.replace(self.base_url, ""), method="POST"
                    )
                    logger.info("Okta Event Hook verification triggered")
                except Exception as verr:
                    logger.warning(
                        "Failed to trigger Okta Event Hook verification: {}", verr
                    )
        except HTTPStatusError as http_err:
            logger.error("HTTP error while creating Okta Event Hook: {}", http_err)
        except Exception as err:
            logger.error("Unexpected error while creating Okta Event Hook: {}", err)
