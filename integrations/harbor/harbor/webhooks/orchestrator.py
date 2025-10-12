"""Harbor Webhook Management - Orchestration Layer.

This module provides high-level webhook orchestration using the unified HarborClient.
It handles business logic like creating webhooks for all projects, permissions checks, etc.
"""
from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean

from ..client.harbor_client import HarborClient
from ..constants import WEBHOOK_EVENTS, WEBHOOK_NAME


class HarborWebhookOrchestrator:
    """
    High-level webhook orchestration for Port Ocean integration.

    This class provides business logic for webhook management,
    using the unified HarborClient for all API operations.
    """

    def __init__(self, client: HarborClient):
        """
        Initialize webhook orchestrator.

        Args:
            client: Configured HarborClient instance
        """
        self.client = client

    async def setup_webhooks_for_integration(
        self,
        app_host: str,
        integration_identifier: str
    ) -> dict[str, Any]:
        """
        Create webhooks for all accessible projects.
        Main method to call during integration setup.

        Args:
            app_host: Base URL of the Port Ocean application
            integration_identifier: Unique identifier for this integration instance

        Returns:
            Dictionary with success/failure counts and details
        """
        webhook_url = f"{app_host}/integration/webhook"
        webhook_name = f"{integration_identifier}-{WEBHOOK_NAME}"

        results = {
            "total_projects": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }

        logger.info("Starting webhook setup for all accessible projects")

        # Check if user is system admin
        is_system_admin = await self.client.has_system_admin_permission()

        # Get all accessible projects
        projects = []
        async for project_batch in self.client.get_paginated_projects({"page_size": 100}):
            projects.extend(project_batch)

        results["total_projects"] = len(projects)

        if not projects:
            logger.warning("No accessible projects found")
            return results

        # Create webhooks for each project
        for project in projects:
            project_name = project.get("name")

            # Check permissions if not system admin
            if not is_system_admin:
                has_permission = await self.client.has_project_admin_permission(project_name)
                if not has_permission:
                    logger.warning(
                        f"Skipping {project_name}: insufficient permissions"
                    )
                    results["skipped"] += 1
                    results["details"].append({
                        "project": project_name,
                        "status": "skipped",
                        "reason": "insufficient_permissions"
                    })
                    continue

            # Create webhook
            try:
                webhook = await self.client.create_project_webhook(
                    project_name,
                    webhook_url,
                    webhook_name,
                    WEBHOOK_EVENTS
                )

                if webhook:
                    results["successful"] += 1
                    results["details"].append({
                        "project": project_name,
                        "status": "success",
                        "webhook_id": webhook.get("id")
                    })
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "project": project_name,
                        "status": "failed",
                        "reason": "creation_failed"
                    })

            except Exception as e:
                logger.error(f"Error creating webhook for {project_name}: {e}")
                results["failed"] += 1
                results["details"].append({
                    "project": project_name,
                    "status": "failed",
                    "reason": str(e)
                })

        logger.info(
            f"Webhook setup completed. "
            f"Success: {results['successful']}, "
            f"Failed: {results['failed']}, "
            f"Skipped: {results['skipped']}"
        )

        return results

    async def cleanup_integration_webhooks(
        self,
        integration_identifier: str
    ) -> dict[str, Any]:
        """
        Remove all Port Ocean webhooks from all accessible projects.
        Useful for cleanup during uninstallation.

        Args:
            integration_identifier: Unique identifier for this integration instance

        Returns:
            Dictionary with cleanup results
        """
        webhook_name_pattern = f"{integration_identifier}-{WEBHOOK_NAME}"

        results = {
            "total_projects": 0,
            "successful": 0,
            "failed": 0,
            "details": []
        }

        logger.info("Starting webhook cleanup for all accessible projects")

        # Get all accessible projects
        projects = []
        async for project_batch in self.client.get_paginated_projects({"page_size": 100}):
            projects.extend(project_batch)

        results["total_projects"] = len(projects)

        for project in projects:
            project_name = project.get("name")

            try:
                # Get webhooks for this project
                webhooks = await self.client.get_project_webhooks(project_name)

                # Find Ocean webhooks
                ocean_webhooks = [
                    w for w in webhooks
                    if webhook_name_pattern in w.get("name", "")
                ]

                # Delete each Ocean webhook
                for webhook in ocean_webhooks:
                    webhook_id = webhook.get("id")
                    success = await self.client.delete_project_webhook(
                        project_name,
                        webhook_id
                    )

                    if success:
                        results["successful"] += 1
                        results["details"].append({
                            "project": project_name,
                            "webhook_id": webhook_id,
                            "status": "deleted"
                        })
                    else:
                        results["failed"] += 1
                        results["details"].append({
                            "project": project_name,
                            "webhook_id": webhook_id,
                            "status": "failed"
                        })

            except Exception as e:
                logger.error(
                    f"Error cleaning up webhooks for {project_name}: {e}")
                results["failed"] += 1
                results["details"].append({
                    "project": project_name,
                    "status": "failed",
                    "reason": str(e)
                })

        logger.info(
            f"Webhook cleanup completed. "
            f"Success: {results['successful']}, "
            f"Failed: {results['failed']}"
        )

        return results

    async def update_webhooks_for_integration(
        self,
        app_host: str,
        integration_identifier: str,
        new_events: list[str]
    ) -> dict[str, Any]:
        """
        Update webhook event subscriptions for all projects.

        Args:
            app_host: Base URL of the Port Ocean application
            integration_identifier: Unique identifier for this integration
            new_events: Updated list of events to subscribe to

        Returns:
            Dictionary with update results
        """
        webhook_url = f"{app_host}/integration/webhook"
        webhook_name = f"{integration_identifier}-{WEBHOOK_NAME}"

        results = {
            "total_webhooks": 0,
            "updated": 0,
            "failed": 0,
            "details": []
        }

        logger.info("Updating webhook configurations")

        # Get all projects
        projects = []
        async for project_batch in self.client.get_paginated_projects({"page_size": 100}):
            projects.extend(project_batch)

        for project in projects:
            project_name = project.get("name")

            try:
                # Get existing webhooks
                webhooks = await self.client.get_project_webhooks(project_name)
                ocean_webhooks = [
                    w for w in webhooks
                    if webhook_name in w.get("name", "")
                ]

                for webhook in ocean_webhooks:
                    webhook_id = webhook.get("id")
                    results["total_webhooks"] += 1

                    updated = await self.client.update_project_webhook(
                        project_name,
                        webhook_id,
                        webhook_url,
                        webhook_name,
                        new_events
                    )

                    if updated:
                        results["updated"] += 1
                        results["details"].append({
                            "project": project_name,
                            "webhook_id": webhook_id,
                            "status": "updated"
                        })
                    else:
                        results["failed"] += 1
                        results["details"].append({
                            "project": project_name,
                            "webhook_id": webhook_id,
                            "status": "failed"
                        })

            except Exception as e:
                logger.error(
                    f"Error updating webhooks for {project_name}: {e}")
                results["failed"] += 1

        logger.info(
            f"Webhook update completed. "
            f"Updated: {results['updated']}, "
            f"Failed: {results['failed']}"
        )

        return results


# ============================================================================
# Convenience function for integration startup
# ============================================================================

async def setup_harbor_webhooks(
    harbor_url: str,
    username: str,
    password: str,
    app_host: str,
    integration_identifier: str
) -> dict[str, Any]:
    """
    Convenience function to setup webhooks during integration startup.

    Args:
        harbor_url: Harbor base URL
        username: Harbor username
        password: Harbor password
        app_host: Port Ocean app host URL
        integration_identifier: Integration identifier

    Returns:
        Setup results dictionary
    """
    client = HarborClient(harbor_url, username, password)
    orchestrator = HarborWebhookOrchestrator(client)

    return await orchestrator.setup_webhooks_for_integration(
        app_host,
        integration_identifier
    )
