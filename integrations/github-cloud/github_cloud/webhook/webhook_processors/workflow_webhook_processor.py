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
        workflow = payload["workflow"]
        action = payload["action"]
        repo = payload["repository"]

        logger.info(
            f"Processing workflow webhook event for workflow {workflow['name']} in repo {repo['full_name']}"
        )

        # For workflow deletion, return the workflow as deleted
        if action == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[workflow],
            )

        # For workflow creation or update, fetch fresh data
        client = GitHubCloudClient.create_from_ocean_configuration()
        try:
            # Get the workflow file content to ensure we have the latest data
            workflow_file = await client.rest.get_file_content(
                repo["full_name"],
                workflow["path"],
                repo["default_branch"]
            )

            # Enrich workflow data with repository info and file content
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
            # Fallback to payload data if fetch fails
            workflow["repo"] = repo["full_name"]
            workflow["repository"] = repo
            return WebhookEventRawResults(
                updated_raw_results=[workflow],
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
        required_fields = ["workflow", "action", "repository"]
        return all(field in payload for field in required_fields)

    async def process(self, payload: Dict[str, Any]) -> List[RawEntityDiff]:
        """
        Process workflow webhook events.

        Args:
            payload: Webhook payload

        Returns:
            List of entity diffs to be processed
        """
        action = payload.get("action")
        if not action:
            logger.warning("No action found in workflow webhook payload")
            return []

        if "workflow_run" in payload:
            return await self._process_workflow_run(payload)
        elif "workflow_job" in payload:
            return await self._process_workflow_job(payload)
        else:
            logger.warning(f"Unknown workflow webhook event type: {payload.keys()}")
            return []

    async def _process_workflow_run(self, payload: Dict[str, Any]) -> List[RawEntityDiff]:
        """
        Process workflow run events.

        Args:
            payload: Webhook payload containing workflow_run data

        Returns:
            List of entity diffs
        """
        workflow_run = payload["workflow_run"]
        repository = payload["repository"]

        # Enrich workflow run with repository data
        enriched_run = {**workflow_run, "repository": repository}

        return [
            {
                "kind": ObjectKind.WORKFLOW_RUN,
                "action": "upsert",
                "entity": enriched_run,
            }
        ]

    async def _process_workflow_job(self, payload: Dict[str, Any]) -> List[RawEntityDiff]:
        """
        Process workflow job events.

        Args:
            payload: Webhook payload containing workflow_job data

        Returns:
            List of entity diffs
        """
        workflow_job = payload["workflow_job"]
        repository = payload["repository"]
        workflow_run = payload.get("workflow_run", {})

        # Enrich workflow job with repository and run data
        enriched_job = {
            **workflow_job,
            "repository": repository,
            "workflow_run": workflow_run,
        }

        return [
            {
                "kind": ObjectKind.WORKFLOW_JOB,
                "action": "upsert",
                "entity": enriched_job,
            }
        ]
