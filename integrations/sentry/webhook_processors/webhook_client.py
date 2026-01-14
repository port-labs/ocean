from clients.sentry import SentryClient
from typing import Any
from clients.exceptions import ResourceNotFoundError
from loguru import logger
import asyncio
import httpx
from webhook_processors.events import ALERT_RULE_CONDITIONS, ALERT_RULE_ACTIONS


class SentryWebhookClient(SentryClient):
    """Handles Sentry Event Hooks operations."""

    async def _get_project_hooks(self, project_slug: str) -> list[dict[str, Any]]:
        """List service hooks for a specific project."""
        url = f"projects/{self.organization}/{project_slug}/hooks/"
        try:
            response = await self.send_api_request("GET", url)
            return response.json()
        except ResourceNotFoundError:
            return []

    async def _create_project_hook(
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
            hooks = await self._get_project_hooks(project_slug)
            if any(hook["url"] == webhook_url for hook in hooks):
                logger.debug(f"Service hook already exists for project {project_slug}")
                return

            logger.info(f"Creating service hook for project {project_slug}")
            await self._create_issue_alert_rule(
                project_slug,
                f"Port Issue Alert - {project_slug}",
            )
            hook: dict[str, Any] = await self._create_project_hook(
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

    async def _get_project_alert_rules(self, project_slug: str) -> list[dict[str, Any]]:
        """List alert rules for a specific project."""
        url = f"projects/{self.organization}/{project_slug}/rules/"
        try:
            response = await self.send_api_request("GET", url)
            return response.json()
        except ResourceNotFoundError:
            return []

    async def _create_project_alert_rule(
        self,
        project_slug: str,
        name: str,
        conditions: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        frequency: int = 30,
        action_match: str = "all",
    ) -> dict[str, Any]:
        """Create a new alert rule for a project."""
        url = f"projects/{self.organization}/{project_slug}/rules/"
        payload = {
            "name": name,
            "conditions": conditions,
            "actions": actions,
            "frequency": frequency,
            "actionMatch": action_match,
        }
        response = await self.send_api_request("POST", url, json=payload)
        return response.json()

    async def _create_issue_alert_rule(
        self,
        project_slug: str,
        rule_name: str,
        conditions: list[dict[str, Any]] = ALERT_RULE_CONDITIONS,
        actions: list[dict[str, Any]] = ALERT_RULE_ACTIONS,
        frequency: int = 30,
        action_match: str = "any",
    ) -> None:
        """Check if an issue alert rule exists and create it if it doesn't."""
        try:
            rules = await self._get_project_alert_rules(project_slug)
            if any(rule["name"] == rule_name for rule in rules):
                logger.debug(
                    f"Alert rule '{rule_name}' already exists for project {project_slug}"
                )
                return

            logger.info(f"Creating alert rule '{rule_name}' for project {project_slug}")
            rule: dict[str, Any] = await self._create_project_alert_rule(
                project_slug, rule_name, conditions, actions, frequency, action_match
            )
            logger.info(
                f"Alert rule '{rule_name}' created for project {project_slug}: {rule["id"]}"
            )
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"Failed to create alert rule '{rule_name}' for project {project_slug}: {e}"
            )
