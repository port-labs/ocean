from typing import Any

from loguru import logger

from harbor.clients.http.client import HarborClient
from harbor.webhooks.events import HarborEventType


class HarborWebhookClient:
    """Client for creating and managing Harbor webhook policies."""

    WEBHOOK_NAME = "Port-Ocean-Harbor-Integration"

    def __init__(self, client: HarborClient, webhook_secret: str | None = None):
        """Initialize webhook client."""
        self.client = client
        self.webhook_secret = webhook_secret

    def _build_webhook_payload(self, webhook_url: str, event_types: list[HarborEventType]) -> dict[str, Any]:
        """Build webhook configuration payload."""
        payload = {
            "name": self.WEBHOOK_NAME,
            "description": "Port Ocean Harbor Integration - Real-time updates",
            "enabled": True,
            "event_types": [str(event) for event in event_types],
            "targets": [
                {
                    "type": "http",
                    "address": webhook_url,
                    "skip_cert_verify": True,
                }
            ],
        }

        if self.webhook_secret:
            payload["targets"][0]["auth_header"] = f"Authorization: Bearer {self.webhook_secret}"

        return payload

    async def get_existing_webhook_id(self, project_name: str) -> int | None:
        """Get the ID of existing Port Ocean webhook if it exists.

        Args:
            project_name: Name of the Harbor project

        Returns:
            Webhook ID or None if not found
        """
        try:
            policies = await self.get_webhook_policies(project_name)

            for policy in policies:
                if policy.get("name") == self.WEBHOOK_NAME:
                    return policy.get("id")

            return None
        except Exception as e:
            logger.warning(f"Error checking webhook ID: {e}")
            return None

    async def get_webhook_policies(self, project_name: str) -> list[dict[str, Any]]:
        """Get existing webhook policies for a project.

        Args:
            project_name: Name of the Harbor project

        Returns:
            List of webhook policies
        """
        logger.debug(f"Fetching webhook policies for project: {project_name}")

        endpoint = f"/projects/{project_name}/webhook/policies"
        return await self.client.send_api_request(endpoint)

    async def create_webhook(
        self,
        project_name: str,
        webhook_url: str,
        event_types: list[HarborEventType],
    ) -> dict[str, Any]:
        """Create a webhook policy for a project.

        Args:
            project_name: Name of the Harbor project
            webhook_url: URL to send webhook events to
            event_types: List of event types to listen for

        Returns:
            Created webhook policy
        """
        logger.info(f"Creating webhook for project: {project_name}")

        endpoint = f"/projects/{project_name}/webhook/policies"

        payload = self._build_webhook_payload(webhook_url, event_types)

        return await self.client.send_api_request(
            endpoint,
            method="POST",
            json_data=payload,
        )

    async def update_webhook(
        self,
        project_name: str,
        webhook_id: int,
        webhook_url: str,
        event_types: list[HarborEventType],
    ) -> dict[str, Any]:
        """Update an existing webhook policy.

        Args:
            project_name: Name of the Harbor project
            webhook_id: ID of the webhook to update
            webhook_url: URL to send webhook events to
            event_types: List of event types to listen for

        Returns:
            Updated webhook policy
        """
        logger.info(f"Updating webhook {webhook_id} for project: {project_name}")

        endpoint = f"/projects/{project_name}/webhook/policies/{webhook_id}"

        payload = self._build_webhook_payload(webhook_url, event_types)

        return await self.client.send_api_request(
            endpoint,
            method="PUT",
            json_data=payload,
        )

    async def upsert_webhook(
        self,
        project_name: str,
        webhook_url: str,
        event_types: list[HarborEventType],
    ) -> None:
        """Create or update webhook policy.

        Args:
            project_name: Name of the Harbor project
            webhook_url: URL to send webhook events to
            event_types: List of event types to listen for
        """
        webhook_id = await self.get_existing_webhook_id(project_name)

        try:
            if webhook_id:
                # update exisiting webhook
                await self.update_webhook(project_name, webhook_id, webhook_url, event_types)
                logger.info(f"Successfully updated webhook for: {project_name}")
            else:
                # otherwise, create new one
                await self.create_webhook(project_name, webhook_url, event_types)
                logger.info(f"Successfully created webhook for: {project_name}")
        except Exception as e:
            logger.error(f"Failed to upsert webhook for {project_name}: {e}")
