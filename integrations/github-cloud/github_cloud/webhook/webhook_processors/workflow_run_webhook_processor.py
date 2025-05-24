from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github_cloud.webhook.webhook_processors._github_abstract_webhook_processor import (
    GitHubCloudAbstractWebhookProcessor,
)
from github_cloud.helpers.utils import ObjectKind
from github_cloud.clients.github_client import GitHubCloudClient


class WorkflowRunWebhookProcessor(GitHubCloudAbstractWebhookProcessor):
    """
    Process workflow run events from GitHub Cloud.
    Handles workflow run started, completed, and other status events.
    """

    events = ["workflow_run"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.WORKFLOW_RUN]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle the workflow run webhook event.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            WebhookEventRawResults containing the processed results
        """
        workflow_run = payload["workflow_run"]
        action = payload["action"]
        repo = payload["repository"]

        logger.info(
            f"Processing workflow run webhook event for run {workflow_run['id']} in repo {repo['full_name']}"
        )

        # For workflow run deletion, return the run as deleted
        if action == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[workflow_run],
            )

        # For workflow run creation or update, fetch fresh data
        client = GitHubCloudClient.create_from_ocean_configuration()
        try:
            # Get fresh workflow run data
            updated_run = await client.get_single_workflow_run(
                repo["full_name"],
                workflow_run["id"]
            )

            if updated_run:
                # Enrich with repository data
                updated_run["repository"] = repo

                # Fetch and add jobs
                jobs = []
                async for jobs_batch in client.get_workflow_jobs(
                    repo["full_name"],
                    workflow_run["id"]
                ):
                    jobs.extend(jobs_batch)
                updated_run["jobs"] = jobs

                return WebhookEventRawResults(
                    updated_raw_results=[updated_run],
                    deleted_raw_results=[],
                )

            # Fallback to payload data if fetch fails
            workflow_run["repository"] = repo
            return WebhookEventRawResults(
                updated_raw_results=[workflow_run],
                deleted_raw_results=[],
            )
        except Exception as e:
            logger.error(f"Failed to fetch workflow run data: {str(e)}")
            # Fallback to payload data if fetch fails
            workflow_run["repository"] = repo
            return WebhookEventRawResults(
                updated_raw_results=[workflow_run],
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
        required_fields = ["workflow_run", "action", "repository"]
        return all(field in payload for field in required_fields)
