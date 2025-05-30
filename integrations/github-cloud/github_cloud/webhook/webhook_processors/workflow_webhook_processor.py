from typing import Dict, Any, List, Set
from loguru import logger
from port_ocean.core.ocean_types import RawEntityDiff
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults, EventPayload
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from github_cloud.helpers.utils import ObjectKind
from github_cloud.webhook.webhook_processors._github_abstract_webhook_processor import GitHubCloudAbstractWebhookProcessor
from github_cloud.clients.github_client import GitHubCloudClient


class WorkflowWebhookProcessor(GitHubCloudAbstractWebhookProcessor):
    """
    Process workflow-related webhook events from GitHub Cloud.
    Handles workflow created/updated/deleted events.
    """

    events = ["workflow"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.WORKFLOW]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle the workflow webhook event.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            WebhookEventRawResults containing the processed results
        """
        # Dispatch based on event type in payload
        if "workflow" in payload:
            workflow = payload["workflow"]
            action = payload["action"]
            repo = payload["repository"]
            logger.info(
                f"Processing workflow webhook event for workflow {workflow['name']} in repo {repo['full_name']}"
            )
            if action == "deleted":
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[workflow],
                )
            client = GitHubCloudClient.create_from_ocean_configuration()
            try:
                workflow_file = await client.rest.get_file_content(
                    repo["full_name"],
                    workflow["path"],
                    repo["default_branch"]
                )
                enriched_workflow = {
                    **workflow,
                    "repo": repo["full_name"],
                    "content": workflow_file if workflow_file else "",
                    "repository": repo
                }
                return WebhookEventRawResults(
                    updated_raw_results=[enriched_workflow],
                    deleted_raw_results=[],
                )
            except Exception as e:
                logger.error(f"Failed to fetch workflow file content: {str(e)}")
                workflow["repo"] = repo["full_name"]
                workflow["repository"] = repo
                return WebhookEventRawResults(
                    updated_raw_results=[workflow],
                    deleted_raw_results=[],
                )
        else:
            logger.error(f"Unknown workflow event type in payload: {payload.keys()}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def validate_payload(self, payload: EventPayload) -> bool:
        """
        Validate the webhook payload.

        Args:
            payload: Event payload

        Returns:
            True if valid, False otherwise
        """
        # Validate based on event type
        if "workflow" in payload:
            required_fields = ["workflow", "action", "repository"]
            return all(field in payload for field in required_fields)
        return False
