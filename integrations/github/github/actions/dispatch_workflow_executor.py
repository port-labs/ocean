import asyncio
from datetime import datetime, timezone
import json

import httpx
from integrations.github.github.actions.utils import build_external_id
from integrations.github.github.context.auth import (
    get_authenticated_user,
)
from integrations.github.github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)
from integrations.github.github.core.options import SingleRepositoryOptions
from integrations.github.github.webhook.registry import (
    WEBHOOK_PATH as DISPATCH_WEBHOOK_PATH,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integrations.github.github.webhook.webhook_processors.base_workflow_run_webhook_processor import (
    BaseWorkflowRunWebhookProcessor,
)
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)
from integrations.github.github.actions.abstract_github_executor import (
    AbstractGithubExecutor,
)


MAX_WORKFLOW_POLL_ATTEMPTS = 10
WORKFLOW_POLL_DELAY_SECONDS = 2


class DispatchWorkflowExecutor(AbstractGithubExecutor):
    ACTION_NAME = "dispatch_workflow"
    PARTITION_KEY = "workflow"

    class DispatchWorkflowWebhookProcessor(BaseWorkflowRunWebhookProcessor):
        @classmethod
        def get_processor_type(cls) -> WebhookProcessorType:
            return WebhookProcessorType.ACTION

        async def _should_process_event(self, event: WebhookEvent) -> bool:
            workflow_run = event.payload["workflow_run"]
            authenticated_user = await get_authenticated_user()
            should_process = (
                await super()._should_process_event(event)
                and workflow_run["status"] == "completed"
                and workflow_run["actor"]["login"] == authenticated_user.login
            )
            return should_process

        async def handle_event(
            self, payload: EventPayload, resource_config: ResourceConfig
        ) -> WebhookEventRawResults:
            workflow_run = payload["workflow_run"]

            external_id = build_external_id(workflow_run)
            action_run: ActionRun[IntegrationActionInvocationPayload] = (
                await ocean.port_client.get_run_by_external_id(external_id)
            )

            if (
                action_run.status == RunStatus.IN_PROGRESS
                and action_run.payload.integrationActionExecutionProperties.get(
                    "reportWorkflowStatus", False
                )
            ):
                status = (
                    RunStatus.SUCCESS
                    if workflow_run["conclusion"] in ["success", "skipped", "neutral"]
                    else RunStatus.FAILURE
                )
                await ocean.port_client.patch_run(action_run.id, {"status": status})

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

    WEBHOOK_PROCESSOR_CLASS = DispatchWorkflowWebhookProcessor
    WEBHOOK_PATH = DISPATCH_WEBHOOK_PATH
    _default_ref_cache: dict[str, str] = {}

    async def _get_default_ref(self, repo: str) -> str:
        if repo in self._default_ref_cache:
            return self._default_ref_cache[repo]

        repoExporter = RestRepositoryExporter(self.rest_client)
        repo = await repoExporter.get_resource(SingleRepositoryOptions(name=repo))
        if not (repo.get("id") and repo.get("default_branch")):
            raise Exception("Failed to get repository data")

        repo_id = repo["id"]
        self._default_ref_cache[repo_id] = repo["default_branch"]
        return self._default_ref_cache[repo_id]

    async def execute(self, run: ActionRun[IntegrationActionInvocationPayload]) -> None:
        repo = run.payload.integrationActionExecutionProperties.get("repo")
        workflow = run.payload.integrationActionExecutionProperties.get("workflow")
        inputs = run.payload.integrationActionExecutionProperties.get(
            "workflowInputs", {}
        )

        if not (repo and workflow):
            raise ValueError("repo and workflow are required")

        ref = await self._get_default_ref(repo)
        try:
            isoDate = datetime.now(timezone.utc).isoformat()
            await self.rest_client.make_request(
                f"{self.rest_client.base_url}/repos/{self.rest_client.organization}/{repo}/actions/workflows/{workflow}/dispatches",
                method="POST",
                json_data={
                    "ref": ref,
                    "inputs": inputs,
                },
                ignore_default_errors=False,
            )

            # Get the workflow run id
            workflow_runs = []
            attempts_made = 0
            while (
                len(workflow_runs) == 0 and attempts_made < MAX_WORKFLOW_POLL_ATTEMPTS
            ):
                authenticated_user = await get_authenticated_user()
                response = await self.rest_client.send_api_request(
                    f"{self.rest_client.base_url}/repos/{self.rest_client.organization}/{repo}/actions/runs",
                    params={
                        "actor": authenticated_user.login,
                        "event": "workflow_dispatch",
                        "created": f">{isoDate}",
                        "exclude_pull_requests": True,
                    },
                    method="GET",
                    ignore_default_errors=False,
                )
                workflow_runs = response.get("workflow_runs", [])
                if len(workflow_runs) == 0:
                    await asyncio.sleep(WORKFLOW_POLL_DELAY_SECONDS)
                    attempts_made += 1

            if len(workflow_runs) == 0:
                raise Exception("No workflow runs found")

            external_id = build_external_id(workflow_runs[0])
            await ocean.port_client.patch_run(run.id, {"external_run_id": external_id})
        except Exception as e:
            error_message = str(e)
            if isinstance(e, httpx.HTTPStatusError):
                error_message = json.loads(e.response.text).get("message", str(e))
            raise Exception(f"Error dispatching workflow: {error_message}")
