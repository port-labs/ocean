import asyncio
from typing import Any, AsyncGenerator

from loguru import logger

from client import TerraformClient, TERRAFORM_WEBHOOK_EVENTS


class TerraformWebhookClient(TerraformClient):
    """Handles Terraform Cloud webhook operations."""

    async def _webhook_exists(self, workspace_id: str, webhook_target_url: str) -> bool:
        """Check if a webhook already exists for the given workspace."""
        endpoint = f"workspaces/{workspace_id}/notification-configurations"
        notifications_response = await self.send_api_request(endpoint=endpoint)
        existing_configs = notifications_response.get("data", [])

        return any(
            config["attributes"]["url"] == webhook_target_url
            for config in existing_configs
        )

    async def _ensure_workspace_webhook(
        self,
        workspace: dict[str, Any],
        webhook_target_url: str,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """
        Ensure webhook exists for a single workspace.

        Args:
            workspace: The workspace data
            webhook_target_url: The target URL for the webhook
            semaphore: Semaphore to limit concurrent operations
        """
        async with semaphore:
            workspace_id = workspace["id"]
            workspace_name = workspace.get("attributes", {}).get("name", workspace_id)

            try:
                if await self._webhook_exists(workspace_id, webhook_target_url):
                    logger.debug(
                        f"Webhook already exists for workspace '{workspace_name}' ({workspace_id})"
                    )
                    return

                await self._create_webhook(
                    workspace_id, workspace_name, webhook_target_url
                )

            except Exception as e:
                logger.error(
                    f"Failed to ensure webhook for workspace '{workspace_name}' ({workspace_id}): {e}"
                )

    async def ensure_workspace_webhooks(
        self, base_url: str, max_concurrent: int = 10
    ) -> None:
        """
        Create webhooks for all workspaces if they don't already exist.

        Args:
            base_url: The base URL of the Ocean app (e.g., https://app.example.com)
            max_concurrent: Maximum number of concurrent webhook operations
        """
        logger.info("Ensuring Terraform Cloud workspace webhooks exist")

        base_url = base_url.strip("/")
        webhook_target_url = f"{base_url}/integration/webhook"
        semaphore = asyncio.Semaphore(max_concurrent)

        async for workspaces in self.get_paginated_workspaces():
            batch_tasks = (
                self._ensure_workspace_webhook(workspace, webhook_target_url, semaphore)
                for workspace in workspaces
            )
            await asyncio.gather(*batch_tasks, return_exceptions=True)

    async def _create_webhook(
        self, workspace_id: str, workspace_name: str, webhook_target_url: str
    ) -> None:
        """Create a webhook configuration for a specific workspace."""
        endpoint = f"workspaces/{workspace_id}/notification-configurations"

        webhook_body = {
            "data": {
                "type": "notification-configuration",
                "attributes": {
                    "destination-type": "generic",
                    "enabled": True,
                    "name": "Port Ocean Integration",
                    "url": webhook_target_url,
                    "triggers": TERRAFORM_WEBHOOK_EVENTS,
                },
            }
        }

        try:
            await self.send_api_request(
                endpoint=endpoint, method="POST", json_data=webhook_body
            )
            logger.info(
                f"Successfully created webhook for workspace '{workspace_name}' ({workspace_id})"
            )
        except Exception as e:
            logger.error(f"Failed to create webhook. Body: {webhook_body}, Error: {e}")
            raise

    async def list_workspace_webhooks(
        self, workspace_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        List all webhook configurations for a workspace.

        Args:
            workspace_id: The ID of the workspace

        Yields:
            Lists of webhook configurations
        """
        endpoint = f"workspaces/{workspace_id}/notification-configurations"
        async for webhooks in self.get_paginated_resources(endpoint):
            yield webhooks
