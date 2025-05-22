from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypeVar

from loguru import logger

from github_cloud.webhook.events import EventConfig
from github_cloud.clients.github_client import GitHubCloudClient

# Type variable for event config types
T = TypeVar('T', bound=EventConfig)


class BaseWebhookFactory(Generic[T], ABC):
    """
    Abstract base class for creating GitHub Cloud webhooks.

    Provides common functionality for webhook creation and management.
    """

    def __init__(self, client: GitHubCloudClient, app_host: str):
        """
        Initialize the webhook factory.

        Args:
            client: GitHub Cloud client
            app_host: Host URL for the application
        """
        self._client = client
        self._app_host = app_host

    async def create(
        self, webhook_url: str, github_webhook_endpoint: str
    ) -> Dict[str, Any]:
        """
        Create a webhook, with built-in existence check.

        Args:
            webhook_url: URL for the webhook callback
            github_webhook_endpoint: GitHub Cloud API endpoint for webhook creation

        Returns:
            Webhook data or empty dict if already exists
        """
        # Check if webhook already exists
        if await self._exists(webhook_url, github_webhook_endpoint):
            logger.info(f"Webhook already exists: {webhook_url}")
            return {}

        # Prepare and send webhook creation request
        try:
            events = self.webhook_events()
            payload = self._build_payload(webhook_url, events)
            response = await self._send_request(github_webhook_endpoint, payload)

            if not self._validate_response(response):
                raise Exception("Invalid webhook response")

            logger.info(f"Created webhook with id {response['id']} at {webhook_url}")
            return response

        except Exception as e:
            logger.error(f"Webhook creation failed: {e}")
            raise

    async def _exists(self, webhook_url: str, github_webhook_endpoint: str) -> bool:
        """
        Check if a webhook with the same URL already exists.

        Args:
            webhook_url: Webhook URL to check
            github_webhook_endpoint: GitHub Cloud API endpoint

        Returns:
            True if webhook exists, False otherwise
        """
        # Get the current webhooks
        webhooks_endpoint = github_webhook_endpoint.replace("/hooks", "/hooks")

        async for hooks_batch in self._client.rest.get_paginated_resource(webhooks_endpoint):
            for hook in hooks_batch:
                # Check config.url for the webhook URL
                if hook.get("config", {}).get("url") == webhook_url:
                    return True
        return False

    def _build_payload(self, webhook_url: str, events: T) -> Dict[str, Any]:
        """
        Build the webhook creation payload.

        Args:
            webhook_url: Webhook URL
            events: Event configuration

        Returns:
            Webhook payload
        """
        return {
            "name": "web",  # Always "web" for webhook service
            "active": True,
            "events": [event for event, enabled in events.to_dict().items() if enabled],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "insecure_ssl": "0"
            }
        }

    def _validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Validate webhook creation response.

        Args:
            response: Response from GitHub Cloud API

        Returns:
            True if valid, False otherwise
        """
        return bool(response and "id" in response and "config" in response and "url" in response["config"])

    async def _send_request(
        self, github_webhook_endpoint: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send webhook creation request.

        Args:
            github_webhook_endpoint: GitHub Cloud API endpoint
            data: Request payload

        Returns:
            Response data
        """
        return await self._client.rest.send_api_request(
            "POST", github_webhook_endpoint, data=data
        )

    @abstractmethod
    def webhook_events(self) -> T:
        """
        Get the webhook events configuration.

        Returns:
            Event configuration
        """
        pass
