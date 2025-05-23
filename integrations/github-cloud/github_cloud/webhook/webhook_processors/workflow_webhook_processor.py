from typing import Dict, Any, List, Set
from loguru import logger
from port_ocean.core.ocean_types import RawEntityDiff
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from github_cloud.helpers.utils import ObjectKind
from github_cloud.webhook.webhook_processors._github_abstract_webhook_processor import GitHubCloudAbstractWebhookProcessor


class WorkflowWebhookProcessor(GitHubCloudAbstractWebhookProcessor):
    """
    Processor for GitHub workflow webhook events.
    Handles workflow_run and workflow_job events.
    """

    def __init__(self, event: WebhookEvent) -> None:
        """
        Initialize the workflow webhook processor.

        Args:
            event: Webhook event
        """
        super().__init__(event)
        self.events = ["workflow_run", "workflow_job"]

    def get_matching_kinds(self) -> Set[str]:
        """
        Get the kinds of entities this processor can handle.

        Returns:
            Set of entity kinds
        """
        return {ObjectKind.WORKFLOW_RUN, ObjectKind.WORKFLOW_JOB}

    async def handle_event(self, payload=None, resource_config: ResourceConfig = None) -> WebhookEventRawResults:
        """
        Handle the webhook event.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            WebhookEventRawResults containing the processed results
        """
        if payload is None:
            payload = self.event.payload
        if not await self.should_process_event(self.event):
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
        if not await self.validate_payload(payload):
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        event_type = self._get_event_type(self.event.headers)
        if event_type == "workflow_run":
            workflow_run = payload["workflow_run"]
            repo_name = payload["repository"]["full_name"]
            run_id = workflow_run["id"]

            # Try to fetch fresh data from GitHub
            updated_run = await self._github_cloud_webhook_client.get_single_workflow_run(repo_name, run_id)
            if updated_run:
                # Enrich with repository data
                updated_run["repository"] = payload["repository"]
                # Fetch and add jobs
                jobs = []
                async for jobs_batch in self._github_cloud_webhook_client.get_workflow_jobs(repo_name, run_id):
                    jobs.extend(jobs_batch)
                updated_run["jobs"] = jobs
                return WebhookEventRawResults(updated_raw_results=[updated_run], deleted_raw_results=[])

            # Fallback to payload data if fetch fails
            workflow_run["repository"] = payload["repository"]
            return WebhookEventRawResults(updated_raw_results=[workflow_run], deleted_raw_results=[])

        elif event_type == "workflow_job":
            workflow_job = payload["workflow_job"]
            repo_name = payload["repository"]["full_name"]
            job_id = workflow_job["id"]
            run_id = workflow_job["run_id"]

            # Try to fetch fresh data from GitHub
            updated_job = await self._github_cloud_webhook_client.get_single_workflow_job(repo_name, job_id)
            if updated_job:
                # Enrich with repository and run data
                updated_job["repository"] = payload["repository"]
                # Fetch run data
                run = await self._github_cloud_webhook_client.get_single_workflow_run(repo_name, run_id)
                if run:
                    updated_job["workflow_run"] = run
                return WebhookEventRawResults(updated_raw_results=[updated_job], deleted_raw_results=[])

            # Fallback to payload data if fetch fails
            workflow_job["repository"] = payload["repository"]
            workflow_job["workflow_run"] = payload.get("workflow_run", {})
            return WebhookEventRawResults(updated_raw_results=[workflow_job], deleted_raw_results=[])

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        event_type = self._get_event_type(self.event.headers)
        if event_type == "workflow_run":
            return "workflow_run" in payload and "repository" in payload
        elif event_type == "workflow_job":
            return "workflow_job" in payload and "repository" in payload
        return False

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
