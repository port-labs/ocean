import asyncio
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from loguru import logger
from integrations.github.github.actions.utils import build_external_id
from integrations.github.github.clients.client_factory import create_github_client
from integrations.github.github.context.auth import authenticated_user
from integrations.github.github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)
from integrations.github.github.core.options import SingleRepositoryOptions
from port_ocean.clients.port.mixins.actions import ActionsClientMixin
from integrations.github.github.webhook.registry import (
    WEBHOOK_PATH as DISPATCH_WEBHOOK_PATH,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integrations.github.github.webhook.webhook_processors.base_workflow_run_webhook_processor import (
    BaseWorkflowRunWebhookProcessor,
)
from port_ocean.core.models import ActionRun, RunStatus
from integrations.github.github.actions.abstract_github_executor import AbstractGithubExecutor


MAX_WORKFLOW_POLL_ATTEMPTS = 10
WORKFLOW_POLL_DELAY = 1


class DispatchWorkflowWebhookProcessor(
    BaseWorkflowRunWebhookProcessor, ActionsClientMixin
):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        workflow_run = event.payload["workflow_run"]
        return (
            await super()._should_process_event(event)
            and workflow_run["status"] == "completed"
            and workflow_run["actor"]["login"] == authenticated_user.login
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        workflow_run = payload["workflow_run"]

        external_id = build_external_id(workflow_run)
        action_run = await self.get_run_by_external_id(external_id)

        if (
            action_run.status == RunStatus.IN_PROGRESS
            and action_run.payload.oceanExecution.get("reportWorkflowStatus", False)
        ):
            status = (
                RunStatus.SUCCESS
                if workflow_run["conclusion"] in ["success", "skipped", "neutral"]
                else RunStatus.FAILURE
            )
            await self.patch_run(action_run.id, {"status": status})

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])


class DispatchWorkflowExecutor(AbstractGithubExecutor, ActionsClientMixin):
    ACTION_NAME = "dispatch_workflow"
    PARTITION_KEY = "workflow"
    WEBHOOK_PROCESSOR_CLASS = DispatchWorkflowWebhookProcessor
    WEBHOOK_PATH = DISPATCH_WEBHOOK_PATH

    @lru_cache
    async def _get_default_ref(self, repo: str) -> str:
        repoExporter = RestRepositoryExporter(self.rest_client)
        repo = await repoExporter.get_resource(SingleRepositoryOptions(name=repo))
        return repo.get("default_branch", "main")

    async def execute(self, run: ActionRun) -> None:
        repo = run.payload.get("repo")
        workflow = run.payload.get("workflow")
        inputs = run.payload.oceanExecution.get("workflowInputs", {})

        if not (repo and workflow):
            raise ValueError("repo and workflow are required")

        ref = await self._get_default_ref(repo)
        try:
            isoDate = datetime.now(timezone.utc).isoformat()
            await self.rest_client.send_api_request(
                f"{self.rest_client.base_url}/repos/{self.rest_client.organization}/{repo}/actions/workflows/{workflow}/dispatches",
                method="POST",
                json={
                    "ref": ref,
                    "inputs": inputs,
                },
            )

            # Get the workflow run id
            workflow_runs = []
            attempts_made = 0
            while len(workflow_runs) == 0 and attempts_made < MAX_WORKFLOW_POLL_ATTEMPTS:
                response = await self.rest_client.send_api_request(
                    f"{self.rest_client.base_url}/repos/{self.rest_client.organization}/{repo}/actions/runs",
                    params={
                        "actor": authenticated_user.login,
                        "event": "workflow_dispatch",
                        "created": f">{isoDate}",
                        "exclude_pull_requests": True,
                    },
                    method="GET",
                )
                workflow_runs = response.get("workflow_runs", [])
                if len(workflow_runs) == 0:
                    await asyncio.sleep(WORKFLOW_POLL_DELAY)
                    attempts_made += 1

            external_id = build_external_id(workflow_runs[0])
            await self.patch_run(run.id, {"external_run_id": external_id})
        except Exception as e:
            logger.error(f"Error dispatching workflow: {e}")
            raise
