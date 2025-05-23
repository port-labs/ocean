from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors._github_abstract_webhook_processor import (
    GitHubAbstractWebhookProcessor,
)


class WorkflowWebhookProcessor(GitHubAbstractWebhookProcessor):
    """
    Processor for GitHub workflow run events.

    Handles events related to workflow execution.
    """

    # GitHub workflow events
    events = ["workflow_run", "workflow_job"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """
        Get the matching object kinds for this event.

        Args:
            event: Webhook event

        Returns:
            List of object kinds
        """
        return [ObjectKind.WORKFLOW]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle a workflow event.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            Processing results
        """
        action = payload.get("action", "")
        repo = payload.get("repository", {})
        repo_name = repo.get("full_name", "")

        # Handle workflow_run events
        if "workflow_run" in payload:
            workflow_run = payload["workflow_run"]
            run_id = workflow_run.get("id")

            logger.info(
                f"Handling workflow_run {action} event for {repo_name} (run {run_id})"
            )

            # Get the full workflow run data from the API
            updated_workflow = await self._github_webhook_client.get_workflow_run(
                repo_name, run_id
            )

            if not updated_workflow:
                logger.warning(f"Could not fetch workflow run {repo_name}#{run_id}")
                updated_workflow = workflow_run

            # Add repository information
            updated_workflow["repository"] = repo

            return WebhookEventRawResults(
                updated_raw_results=[updated_workflow],
                deleted_raw_results=[],
            )

        # Handle workflow_job events
        elif "workflow_job" in payload:
            workflow_job = payload["workflow_job"]
            job_id = workflow_job.get("id")

            logger.info(
                f"Handling workflow_job {action} event for {repo_name} (job {job_id})"
            )

            # Get the full workflow job data from the API
            updated_job = await self._github_webhook_client.get_workflow_job(
                repo_name, job_id
            )

            if not updated_job:
                logger.warning(f"Could not fetch workflow job {repo_name}#{job_id}")
                updated_job = workflow_job

            # Add repository information
            updated_job["repository"] = repo

            return WebhookEventRawResults(
                updated_raw_results=[updated_job],
                deleted_raw_results=[],
            )

        # Unknown workflow event
        logger.warning(f"Unknown workflow event structure in payload")
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """
        Validate the webhook payload.

        Args:
            payload: Event payload

        Returns:
            True if valid, False otherwise
        """
        return ("workflow_run" in payload or "workflow_job" in payload) and "repository" in payload
