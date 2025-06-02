from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from github.webhook.webhook_processors._github_abstract_webhook_processor import (
    _GitHubAbstractWebhookProcessor,
)


class WorkflowWebhookProcessor(_GitHubAbstractWebhookProcessor):
    events = ["completed", "requested"]
    hooks = ["workflow_run"]

    async def _process_webhook_event(self, event: WebhookEvent) -> None:
        """Process workflow-related webhook events."""
        workflow_data = event.payload.get("workflow", {})
        action = event.payload.get("action")

        if action in ["requested", "completed"]:
            logger.info(
                f"Processing workflow {action} event for workflow {workflow_data.get('name', 'unknown')}"
            )

            # Update or create workflow record in Port
            # This would typically involve calling the Port API
            # to upsert the workflow entity

        elif action == "deleted":
            logger.info(
                f"Processing workflow deletion for workflow {workflow_data.get('name', 'unknown')}"
            )

            # Delete workflow record from Port
            # This would typically involve calling the Port API
            # to delete the workflow entity
