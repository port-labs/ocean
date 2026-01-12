from clients.sentry import SentryClient
from typing import Any
from clients.exceptions import ResourceNotFoundError
from loguru import logger
import asyncio


class SentryWebhookClient(SentryClient):
    """Handles Sentry Event Hooks operations."""

    async def get_project_hooks(self, project_slug: str) -> list[dict[str, Any]]:
        """List service hooks for a specific project."""
        url = f"projects/{self.organization}/{project_slug}/hooks/"
        try:
            response = await self.send_api_request("GET", url)
            return response.json()
        except ResourceNotFoundError:
            return []

    async def create_project_hook(
        self, project_slug: str, hook_url: str, events: list[str]
    ) -> dict[str, Any]:
        """Register a new service hook for a project."""
        url = f"projects/{self.organization}/{project_slug}/hooks/"
        payload = {"url": hook_url, "events": events}
        response = await self.send_api_request("POST", url, json=payload)
        return response.json()

    async def _check_and_create_project_hook(
        self, project_slug: str, webhook_url: str
    ) -> None:
        """Check if a service hook exists for a project and create it if it doesn't."""
        try:
            hooks = await self.get_project_hooks(project_slug)
            if any(hook["url"] == webhook_url for hook in hooks):
                logger.debug(f"Service hook already exists for project {project_slug}")
                return

            logger.info(f"Creating service hook for project {project_slug}")
            hook: dict[str, Any] = await self.create_project_hook(
                project_slug,
                webhook_url,
                ["event.alert", "event.created"],
            )
            logger.info(f"Service hook created for project {project_slug}: {hook}")
        except Exception as e:
            logger.error(
                f"Failed to create service hook for project {project_slug}: {e}"
            )

    async def ensure_service_hooks(self, base_url: str) -> None:
        """Ensure service hooks exist for all projects."""

        logger.info("Ensuring Sentry service hooks exist for all projects")
        webhook_url = f"{base_url.rstrip('/')}/integration/webhook"
        async for projects in self.get_paginated_projects():
            tasks = [
                self._check_and_create_project_hook(project["slug"], webhook_url)
                for project in projects
            ]
            await asyncio.gather(*tasks)
