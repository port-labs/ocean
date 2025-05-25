from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypeVar
import httpx

from loguru import logger

from github.webhook.events import EventConfig
from github.clients.github_client import GitHubClient

T = TypeVar('T', bound=EventConfig)

class BaseWebhookFactory(Generic[T], ABC):
    """
    Abstract base class for creating GitHub webhooks.

    Provides common functionality for webhook creation and management.
    """

    def __init__(self, client: GitHubClient, app_host: str):
        """
        Initialize the webhook factory.

        Args:
            client: GitHub client
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
            github_webhook_endpoint: GitHub API endpoint for webhook creation

        Returns:
            Webhook data or empty dict if already exists
        """
        if await self._exists(webhook_url, github_webhook_endpoint):
            logger.info(f"Webhook already exists: {webhook_url}")
            return {}

        events = self.webhook_events()
        payload = self._build_payload(webhook_url, events)
        response = await self._send_request(github_webhook_endpoint, payload)
        response = response.json() if isinstance(response, httpx.Response) else response
        if not self._validate_response(response):
            raise Exception("Invalid webhook response")

        logger.info(f"Created webhook with id {response['id']} at {webhook_url}")

        return response

    async def _exists(self, webhook_url: str, github_webhook_endpoint: str) -> bool:
        """
        Check if a webhook with the same URL already exists.

        Args:
            webhook_url: Webhook URL to check
            github_webhook_endpoint: GitHub API endpoint

        Returns:
            True if webhook exists, False otherwise
        """
        async for hooks_batch in self._client.rest.get_paginated_resource(github_webhook_endpoint):
            for hook in hooks_batch:
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
            response: Response from GitHub API

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
            github_webhook_endpoint: GitHub API endpoint
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
