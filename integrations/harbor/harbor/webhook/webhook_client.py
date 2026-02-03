from typing import Any, Dict, List
from loguru import logger
from harbor.clients.http.harbor_client import HarborClient
from httpx import HTTPStatusError


class HarborWebhookClient:
    """Client for managing Harbor webhook policies."""

    def __init__(self, client: HarborClient, webhook_secret: str | None = None):
        self.client = client
        self.webhook_secret = webhook_secret

    def _build_webhook_payload(
        self,
        webhook_url: str,
        event_types: List[str],
    ) -> Dict[str, Any]:
        """Build a webhook payload for a project."""
        return {
            "enabled": True,
            "name": "Port Ocean Integration",
            "description": "Port Ocean integration webhook",
            "targets": [
                {
                    "type": "http",
                    "address": webhook_url,
                    "auth_header": self.webhook_secret if self.webhook_secret else "",
                    "skip_cert_verify": False,
                }
            ],
            "event_types": event_types,
        }

    async def _get_existing_webhooks(
        self, project_name: str, webhook_url: str
    ) -> Dict[str, Any] | None:
        """Get all webhook policies for a project."""
        async for webhook_policies in self.client.send_paginated_request(
            f"/projects/{project_name}/webhook/policies",
        ):
            existing_webhook = next(
                (
                    webhook
                    for webhook in webhook_policies
                    if webhook.get("targets")
                    and webhook["targets"][0]["address"] == webhook_url
                ),
                None,
            )

            if existing_webhook:
                return existing_webhook

        return None

    async def _create_webhook_policy(
        self,
        project_name: str,
        webhook_url: str,
        event_types: List[str],
    ) -> None:
        """Create a new webhook policy for a project."""
        webhook_payload = self._build_webhook_payload(webhook_url, event_types)

        logger.info(f"Creating webhook policy for project {project_name}")
        await self.client.make_request(
            f"/projects/{project_name}/webhook/policies",
            method="POST",
            json_data=webhook_payload,
        )
        logger.info(f"Successfully created webhook policy for project {project_name}")

    async def _update_webhook_policy(
        self,
        project_name: str,
        webhook_id: str,
        webhook_url: str,
        event_types: List[str],
    ) -> None:
        """Update a webhook policy for a project."""
        webhook_payload = self._build_webhook_payload(webhook_url, event_types)

        logger.info(f"Updating webhook policy for project {project_name}")
        await self.client.make_request(
            f"/projects/{project_name}/webhook/policies/{webhook_id}",
            method="PUT",
            json_data=webhook_payload,
        )

        logger.info(f"Successfully updated webhook policy for project {project_name}")

    async def upsert_webhook(
        self,
        base_url: str,
        project_name: str,
        webhook_events: List[str],
    ) -> None:
        """Create or update webhook policy for a project."""
        webhook_url = f"{base_url}/webhook"

        try:
            existing_webhook = await self._get_existing_webhooks(
                project_name, webhook_url
            )

            if not existing_webhook:
                logger.info(
                    f"No existing webhook found for project {project_name}, creating new one"
                )

                await self._create_webhook_policy(
                    project_name, webhook_url, webhook_events
                )
                return

            existing_webhook_id = existing_webhook["id"]
            existing_webhook_secret = existing_webhook["targets"][0].get("auth_header")

            logger.info(f"Found existing webhook with ID: {existing_webhook_id}")

            if bool(self.webhook_secret) ^ bool(existing_webhook_secret):
                await self._update_webhook_policy(
                    project_name, existing_webhook_id, webhook_url, webhook_events
                )
                return

            logger.info("Webhook already exists with appropriate configuration")

        except HTTPStatusError as http_err:
            logger.error(
                f"HTTP error occurred while creating webhook for project {project_name}: {http_err}"
            )

        except Exception as e:
            logger.error(f"Failed to upsert webhook for project {project_name}: {e}")
