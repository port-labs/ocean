from abc import ABC, abstractmethod
from typing import Any, Dict

from loguru import logger

from gitlab.webhook.events import EventConfig
from gitlab.clients.gitlab_client import GitLabClient


class BaseWebhookFactory[T: EventConfig](ABC):
    """
    Abstract base class for creating GitLab webhooks.

    Provides a template method for webhook creation with common validation
    and error handling steps.

    Design is driven by Gitlab's Webhook architecture: https://docs.gitlab.com/ee/development/webhooks.html
    """

    def __init__(self, client: GitLabClient, app_host: str):
        self._client = client
        self._app_host = app_host

    async def create(
        self, webhook_url: str, gitlab_webhook_endpoint: str
    ) -> Dict[str, Any]:
        """
        Create a webhook, with built-in existence check.

        Returns:
            Dictionary with webhook details or empty dict if already exists

        Raises:
            Exception: If webhook creation fails
        """
        # Check if webhook already exists
        if await self._exists(webhook_url, gitlab_webhook_endpoint):
            logger.info(f"Webhook already exists: {webhook_url}")
            return {}

        # Prepare and send webhook creation request
        try:
            events = self.webhook_events()
            payload = self._build_payload(webhook_url, events)
            response = await self._send_request(gitlab_webhook_endpoint, payload)

            if not self._validate_response(response):
                raise Exception("Invalid webhook response")

            logger.info(f"Created webhook with id {response['id']} at {webhook_url}")
            return response

        except Exception as e:
            logger.error(f"Webhook creation failed: {e}")
            raise

    async def _exists(self, webhook_url: str, gitlab_webhook_endpoint: str) -> bool:
        """
        Check if a webhook with the same URL already exists.

        Returns:
            Boolean indicating webhook existence
        """
        async for hooks_batch in self._client.rest.get_paginated_resource(
            gitlab_webhook_endpoint
        ):
            if any(hook["url"] == webhook_url for hook in hooks_batch):
                return True
        return False

    def _build_payload(self, webhook_url: str, events: T) -> Dict[str, Any]:
        return {"url": webhook_url, **events.to_dict()}

    def _validate_response(self, response: Dict[str, Any]) -> bool:
        return bool(response and "id" in response and "url" in response)

    async def _send_request(
        self, gitlab_webhook_endpoint: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Abstract method to send webhook creation request.

        Args:
            data: Payload for webhook creation
            webhook_endpoint: GitLab webhook endpoint
        Returns:
            API response dictionary
        """
        return await self._client.rest.send_api_request(
            "POST", gitlab_webhook_endpoint, data=data
        )

    @abstractmethod
    def webhook_events(self) -> T:
        """Provide default events configuration for this webhook type."""
        ...
