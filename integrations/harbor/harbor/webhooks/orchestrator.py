"""Harbor Webhook Management - Orchestration Layer.

This module provides high-level webhook orchestration using the unified HarborClient.
It handles business logic like creating webhooks for all projects, permissions checks, etc.
"""
from typing import Any, Callable, Awaitable
from loguru import logger

from ..client.harbor_client import HarborClient
from ..constants import DEFAULT_PAGE_SIZE, WEBHOOK_EVENTS, WEBHOOK_NAME


class HarborWebhookOrchestrator:
    """
    High-level webhook orchestration for Port Ocean integration.

    This class provides business logic for webhook management,
    using the unified HarborClient for all API operations.
    """

    def __init__(self, client: HarborClient) -> None:
        """Initialize webhook orchestrator."""
        self.client = client
        logger.info(
            "Initialized HarborWebhookOrchestrator",
            extra={
                "component": "webhook_orchestrator",
                "harbor_url": client.harbor_url
            }
        )

    async def _get_all_projects(self) -> list[dict[str, Any]]:
        """Fetch all accessible projects."""
        logger.debug(
            "Fetching all accessible projects",
            extra={
                "component": "webhook_orchestrator",
                "operation": "get_projects",
                "page_size": DEFAULT_PAGE_SIZE
            }
        )

        projects: list[dict[str, Any]] = []
        async for project_batch in self.client.get_paginated_projects(
            {"page_size": DEFAULT_PAGE_SIZE}
        ):
            projects.extend(project_batch)

        logger.info(
            "Successfully fetched projects",
            extra={
                "component": "webhook_orchestrator",
                "operation": "get_projects",
                "project_count": len(projects)
            }
        )
        return projects

    def _validate_project_name(self, project: dict[str, Any]) -> str | None:
        """Validate and extract project name from project dict."""
        project_name = project.get("name")
        if not project_name or not isinstance(project_name, str):
            logger.warning(
                "Invalid project name encountered",
                extra={
                    "component": "webhook_orchestrator",
                    "operation": "validate_project",
                    "project_name": project_name,
                    "project_id": project.get("project_id"),
                    "validation_failed": True
                }
            )
            return None

        logger.debug(
            "Project name validated successfully",
            extra={
                "component": "webhook_orchestrator",
                "operation": "validate_project",
                "project_name": project_name
            }
        )
        return project_name

    def _validate_webhook_id(self, webhook_id: Any, project_name: str) -> int | None:
        """Validate webhook ID is an integer."""
        if not isinstance(webhook_id, int):
            logger.warning(
                "Invalid webhook ID encountered",
                extra={
                    "component": "webhook_orchestrator",
                    "operation": "validate_webhook_id",
                    "project_name": project_name,
                    "webhook_id": webhook_id,
                    "webhook_id_type": type(webhook_id).__name__,
                    "validation_failed": True
                }
            )
            return None

        logger.debug(
            "Webhook ID validated successfully",
            extra={
                "component": "webhook_orchestrator",
                "operation": "validate_webhook_id",
                "project_name": project_name,
                "webhook_id": webhook_id
            }
        )
        return webhook_id

    def _build_webhook_config(self, integration_identifier: str, app_host: str) -> tuple[str, str]:
        """Build webhook URL and name from integration config."""
        webhook_url = f"{app_host}/integration/webhook"
        webhook_name = f"{integration_identifier}-{WEBHOOK_NAME}"

        logger.debug(
            "Built webhook configuration",
            extra={
                "component": "webhook_orchestrator",
                "operation": "build_config",
                "integration_identifier": integration_identifier,
                "webhook_url": webhook_url,
                "webhook_name": webhook_name
            }
        )
        return webhook_url, webhook_name

    def _initialize_results(self, include_skipped: bool = False) -> dict[str, Any]:
        """Initialize results dictionary."""
        results: dict[str, Any] = {
            "total_projects": 0,
            "successful": 0,
            "failed": 0,
            "details": []
        }
        if include_skipped:
            results["skipped"] = 0

        logger.debug(
            "Initialized results dictionary",
            extra={
                "component": "webhook_orchestrator",
                "operation": "initialize_results",
                "include_skipped": include_skipped
            }
        )
        return results

    def _log_completion(self, operation: str, results: dict[str, Any]) -> None:
        """Log operation completion summary."""
        message_parts = [
            f"{operation.capitalize()} completed.",
            f"Success: {results['successful']}",
            f"Failed: {results['failed']}"
        ]
        if "skipped" in results:
            message_parts.append(f"Skipped: {results['skipped']}")

        logger.info(
            " ".join(message_parts),
            extra={
                "component": "webhook_orchestrator",
                "operation": operation,
                "total_projects": results.get("total_projects", 0),
                "successful": results["successful"],
                "failed": results["failed"],
                "skipped": results.get("skipped", 0),
                "total_webhooks": results.get("total_webhooks"),
                "updated": results.get("updated"),
                "completion_status": "success" if results["failed"] == 0 else "partial_failure"
            }
        )

    async def _process_projects(
        self,
        projects: list[dict[str, Any]],
        processor: Callable[[str], Awaitable[dict[str, Any]]],
        results: dict[str, Any]
    ) -> None:
        """Process all projects with a given processor function."""
        logger.debug(
            "Starting project processing",
            extra={
                "component": "webhook_orchestrator",
                "operation": "process_projects",
                "project_count": len(projects)
            }
        )

        for project in projects:
            project_name = self._validate_project_name(project)
            if not project_name:
                results["failed"] += 1
                results["details"].append({
                    "project": str(project.get("name")),
                    "status": "failed",
                    "reason": "invalid_project_name"
                })
                continue

            try:
                logger.debug(
                    "Processing project",
                    extra={
                        "component": "webhook_orchestrator",
                        "operation": "process_project",
                        "project_name": project_name
                    }
                )

                result = await processor(project_name)
                if result.get("success"):
                    results["successful"] += result.get("count", 1)
                else:
                    results["failed"] += result.get("count", 1)

                if "details" in result:
                    results["details"].extend(result["details"])
                elif "detail" in result:
                    results["details"].append(result["detail"])

                logger.debug(
                    "Project processed successfully",
                    extra={
                        "component": "webhook_orchestrator",
                        "operation": "process_project",
                        "project_name": project_name,
                        "success": result.get("success"),
                        "count": result.get("count", 0)
                    }
                )

            except Exception as e:
                logger.error(
                    "Error processing project",
                    extra={
                        "component": "webhook_orchestrator",
                        "operation": "process_project",
                        "project_name": project_name,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                results["failed"] += 1
                results["details"].append({
                    "project": project_name,
                    "status": "failed",
                    "reason": str(e)
                })

    async def _check_project_permission(self, project_name: str, is_system_admin: bool) -> bool:
        """Check if user has permission to modify project webhooks."""
        logger.debug(
            "Checking project permissions",
            extra={
                "component": "webhook_orchestrator",
                "operation": "check_permission",
                "project_name": project_name,
                "is_system_admin": is_system_admin
            }
        )

        if is_system_admin:
            logger.debug(
                "Permission granted - system admin",
                extra={
                    "component": "webhook_orchestrator",
                    "operation": "check_permission",
                    "project_name": project_name,
                    "permission_type": "system_admin"
                }
            )
            return True

        has_permission = await self.client.has_project_admin_permission(project_name)
        logger.debug(
            "Permission check completed",
            extra={
                "component": "webhook_orchestrator",
                "operation": "check_permission",
                "project_name": project_name,
                "has_permission": has_permission,
                "permission_type": "project_admin"
            }
        )
        return has_permission

    async def _create_webhook_for_project(
        self,
        project_name: str,
        webhook_url: str,
        webhook_name: str,
        is_system_admin: bool
    ) -> dict[str, Any]:
        """
        Create webhook for a single project.

        Args:
            project_name: Name of the project
            webhook_url: URL for the webhook
            webhook_name: Name for the webhook
            is_system_admin: Whether user is system admin

        Returns:
            Result dictionary with success status and details
        """
        logger.info(
            "Creating webhook for project",
            extra={
                "component": "webhook_orchestrator",
                "operation": "create_webhook",
                "project_name": project_name,
                "webhook_url": webhook_url,
                "webhook_name": webhook_name
            }
        )

        # Check permissions
        has_permission = await self._check_project_permission(project_name, is_system_admin)
        if not has_permission:
            logger.warning(
                "Insufficient permissions to create webhook",
                extra={
                    "component": "webhook_orchestrator",
                    "operation": "create_webhook",
                    "project_name": project_name,
                    "reason": "insufficient_permissions"
                }
            )
            return {
                "success": False,
                "count": 0,
                "skipped": True,
                "detail": {
                    "project": project_name,
                    "status": "skipped",
                    "reason": "insufficient_permissions"
                }
            }

        webhook = await self.client.create_project_webhook(
            project_name,
            webhook_url,
            webhook_name,
            WEBHOOK_EVENTS
        )

        if webhook:
            webhook_id = webhook.get("id")
            logger.info(
                "Webhook created successfully",
                extra={
                    "component": "webhook_orchestrator",
                    "operation": "create_webhook",
                    "project_name": project_name,
                    "webhook_id": webhook_id,
                    "webhook_name": webhook_name,
                    "status": "success"
                }
            )
            return {
                "success": True,
                "count": 1,
                "detail": {
                    "project": project_name,
                    "status": "success",
                    "webhook_id": webhook_id
                }
            }
        else:
            logger.error(
                "Webhook creation failed",
                extra={
                    "component": "webhook_orchestrator",
                    "operation": "create_webhook",
                    "project_name": project_name,
                    "webhook_name": webhook_name,
                    "status": "failed",
                    "reason": "creation_failed"
                }
            )
            return {
                "success": False,
                "count": 1,
                "detail": {
                    "project": project_name,
                    "status": "failed",
                    "reason": "creation_failed"
                }
            }

    async def _cleanup_webhooks_for_project(
        self,
        project_name: str,
        webhook_name_pattern: str
    ) -> dict[str, Any]:
        """
        Clean up webhooks for a single project.

        Args:
            project_name: Name of the project
            webhook_name_pattern: Pattern to match webhook names

        Returns:
            Result dictionary with success status and details
        """
        logger.info(
            "Starting webhook cleanup for project",
            extra={
                "component": "webhook_orchestrator",
                "operation": "cleanup_webhooks",
                "project_name": project_name,
                "webhook_name_pattern": webhook_name_pattern
            }
        )

        webhooks = await self.client.get_project_webhooks(project_name)

        ocean_webhooks = [
            hook for hook in webhooks
            if webhook_name_pattern in hook.get("name", "")
        ]

        logger.debug(
            "Found webhooks matching pattern",
            extra={
                "component": "webhook_orchestrator",
                "operation": "cleanup_webhooks",
                "project_name": project_name,
                "total_webhooks": len(webhooks),
                "matching_webhooks": len(ocean_webhooks)
            }
        )

        if not ocean_webhooks:
            return {"success": True, "count": 0, "details": []}

        success_count = 0
        failed_count = 0
        details = []

        for webhook in ocean_webhooks:
            webhook_id = self._validate_webhook_id(
                webhook.get("id"), project_name)
            if webhook_id is None:
                failed_count += 1
                details.append({
                    "project": project_name,
                    "webhook_id": webhook.get("id"),
                    "status": "failed",
                    "reason": "invalid_webhook_id"
                })
                continue

            logger.debug(
                "Deleting webhook",
                extra={
                    "component": "webhook_orchestrator",
                    "operation": "delete_webhook",
                    "project_name": project_name,
                    "webhook_id": webhook_id
                }
            )

            success = await self.client.delete_project_webhook(project_name, webhook_id)

            if success:
                success_count += 1
                details.append({
                    "project": project_name,
                    "webhook_id": webhook_id,
                    "status": "deleted"
                })
                logger.info(
                    "Webhook deleted successfully",
                    extra={
                        "component": "webhook_orchestrator",
                        "operation": "delete_webhook",
                        "project_name": project_name,
                        "webhook_id": webhook_id,
                        "status": "success"
                    }
                )
            else:
                failed_count += 1
                details.append({
                    "project": project_name,
                    "webhook_id": webhook_id,
                    "status": "failed"
                })
                logger.error(
                    "Webhook deletion failed",
                    extra={
                        "component": "webhook_orchestrator",
                        "operation": "delete_webhook",
                        "project_name": project_name,
                        "webhook_id": webhook_id,
                        "status": "failed"
                    }
                )

        logger.info(
            "Webhook cleanup completed for project",
            extra={
                "component": "webhook_orchestrator",
                "operation": "cleanup_webhooks",
                "project_name": project_name,
                "success_count": success_count,
                "failed_count": failed_count,
                "total_processed": success_count + failed_count
            }
        )

        return {
            "success": success_count > 0 and failed_count == 0,
            "count": success_count if success_count > failed_count else failed_count,
            "details": details
        }

    async def _update_webhooks_for_project(
        self,
        project_name: str,
        webhook_name: str,
        webhook_url: str,
        new_events: list[str]
    ) -> dict[str, Any]:
        """
        Update webhooks for a single project.

        Args:
            project_name: Name of the project
            webhook_name: Name to match webhooks
            webhook_url: New webhook URL
            new_events: Updated list of events

        Returns:
            Result dictionary with success status and details
        """
        logger.info(
            "Starting webhook update for project",
            extra={
                "component": "webhook_orchestrator",
                "operation": "update_webhooks",
                "project_name": project_name,
                "webhook_name": webhook_name,
                "event_count": len(new_events)
            }
        )

        webhooks = await self.client.get_project_webhooks(project_name)

        ocean_webhooks = [
            w for w in webhooks
            if webhook_name in w.get("name", "")
        ]

        logger.debug(
            "Found webhooks to update",
            extra={
                "component": "webhook_orchestrator",
                "operation": "update_webhooks",
                "project_name": project_name,
                "total_webhooks": len(webhooks),
                "matching_webhooks": len(ocean_webhooks)
            }
        )

        if not ocean_webhooks:
            return {"success": True, "count": 0, "details": []}

        success_count = 0
        failed_count = 0
        details = []

        for webhook in ocean_webhooks:
            webhook_id = self._validate_webhook_id(
                webhook.get("id"), project_name)
            if webhook_id is None:
                failed_count += 1
                continue

            logger.debug(
                "Updating webhook",
                extra={
                    "component": "webhook_orchestrator",
                    "operation": "update_webhook",
                    "project_name": project_name,
                    "webhook_id": webhook_id,
                    "new_events": new_events
                }
            )

            updated = await self.client.update_project_webhook(
                project_name,
                webhook_id,
                webhook_url,
                webhook_name,
                new_events
            )

            if updated:
                success_count += 1
                details.append({
                    "project": project_name,
                    "webhook_id": webhook_id,
                    "status": "updated"
                })
                logger.info(
                    "Webhook updated successfully",
                    extra={
                        "component": "webhook_orchestrator",
                        "operation": "update_webhook",
                        "project_name": project_name,
                        "webhook_id": webhook_id,
                        "status": "success"
                    }
                )
            else:
                failed_count += 1
                details.append({
                    "project": project_name,
                    "webhook_id": webhook_id,
                    "status": "failed"
                })
                logger.error(
                    "Webhook update failed",
                    extra={
                        "component": "webhook_orchestrator",
                        "operation": "update_webhook",
                        "project_name": project_name,
                        "webhook_id": webhook_id,
                        "status": "failed"
                    }
                )

        logger.info(
            "Webhook update completed for project",
            extra={
                "component": "webhook_orchestrator",
                "operation": "update_webhooks",
                "project_name": project_name,
                "success_count": success_count,
                "failed_count": failed_count,
                "total_processed": success_count + failed_count
            }
        )

        return {
            "success": success_count > 0 and failed_count == 0,
            "count": success_count if success_count > failed_count else failed_count,
            "details": details
        }

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
        logger.info(
            "Starting webhook setup for integration",
            extra={
                "component": "webhook_orchestrator",
                "operation": "setup_webhooks",
                "integration_identifier": integration_identifier,
                "app_host": app_host
            }
        )

        webhook_url, webhook_name = self._build_webhook_config(
            integration_identifier, app_host)
        results = self._initialize_results(include_skipped=True)

        # Get all projects and check admin status
        is_system_admin = await self.client.has_system_admin_permission()
        logger.info(
            "System admin check completed",
            extra={
                "component": "webhook_orchestrator",
                "operation": "setup_webhooks",
                "is_system_admin": is_system_admin
            }
        )

        projects = await self._get_all_projects()
        results["total_projects"] = len(projects)

        if not projects:
            logger.warning(
                "No accessible projects found",
                extra={
                    "component": "webhook_orchestrator",
                    "operation": "setup_webhooks",
                    "project_count": 0
                }
            )
            return results

        # Process each project
        for project in projects:
            project_name = self._validate_project_name(project)
            if not project_name:
                results["skipped"] += 1
                results["details"].append({
                    "project": str(project.get("name")),
                    "status": "skipped",
                    "reason": "invalid_project_name"
                })
                continue

            try:
                result = await self._create_webhook_for_project(
                    project_name,
                    webhook_url,
                    webhook_name,
                    is_system_admin
                )

                if result.get("skipped"):
                    results["skipped"] += 1
                elif result.get("success"):
                    results["successful"] += result.get("count", 1)
                else:
                    results["failed"] += result.get("count", 1)

                if "detail" in result:
                    results["details"].append(result["detail"])

            except Exception as e:
                logger.error(
                    "Error creating webhook for project",
                    extra={
                        "component": "webhook_orchestrator",
                        "operation": "setup_webhooks",
                        "project_name": project_name,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                results["failed"] += 1
                results["details"].append({
                    "project": project_name,
                    "status": "failed",
                    "reason": str(e)
                })

        self._log_completion("webhook setup", results)
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
        logger.info(
            "Starting webhook cleanup for integration",
            extra={
                "component": "webhook_orchestrator",
                "operation": "cleanup_integration",
                "integration_identifier": integration_identifier
            }
        )

        webhook_name_pattern = f"{integration_identifier}-{WEBHOOK_NAME}"
        results = self._initialize_results()

        projects = await self._get_all_projects()
        results["total_projects"] = len(projects)

        await self._process_projects(
            projects,
            lambda pn: self._cleanup_webhooks_for_project(
                pn, webhook_name_pattern),
            results
        )

        self._log_completion("webhook cleanup", results)
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
        logger.info(
            "Starting webhook update for integration",
            extra={
                "component": "webhook_orchestrator",
                "operation": "update_integration",
                "integration_identifier": integration_identifier,
                "app_host": app_host,
                "event_count": len(new_events),
                "events": new_events
            }
        )

        webhook_url, webhook_name = self._build_webhook_config(
            integration_identifier, app_host)
        results = self._initialize_results()
        results["total_webhooks"] = 0
        results["updated"] = results.pop("successful")  # Rename for clarity

        projects = await self._get_all_projects()

        for project in projects:
            project_name = self._validate_project_name(project)
            if not project_name:
                results["failed"] += 1
                continue

            try:
                result = await self._update_webhooks_for_project(
                    project_name,
                    webhook_name,
                    webhook_url,
                    new_events
                )

                results["total_webhooks"] += len(result.get("details", []))

                if result.get("success"):
                    results["updated"] += result.get("count", 0)
                else:
                    results["failed"] += result.get("count", 0)

                if "details" in result:
                    results["details"].extend(result["details"])

            except Exception as e:
                logger.error(
                    "Error updating webhooks for project",
                    extra={
                        "component": "webhook_orchestrator",
                        "operation": "update_integration",
                        "project_name": project_name,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                results["failed"] += 1

        logger.info(
            "Webhook update completed for integration",
            extra={
                "component": "webhook_orchestrator",
                "operation": "update_integration",
                "total_webhooks": results["total_webhooks"],
                "updated": results["updated"],
                "failed": results["failed"]
            }
        )

        return results
