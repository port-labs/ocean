import asyncio
from datetime import datetime, timezone
import json

import httpx
from loguru import logger
from github.actions.utils import build_external_id
from github.context.auth import (
    get_authenticated_user,
)
from github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)
from github.core.options import SingleRepositoryOptions
from github.webhook.registry import (
    WEBHOOK_PATH as DISPATCH_WEBHOOK_PATH,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.queue.group_queue import MaybeStr
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.base_workflow_run_webhook_processor import (
    BaseWorkflowRunWebhookProcessor,
)
from port_ocean.core.models import (
    ActionRun,
    RunStatus,
)
from github.actions.abstract_github_executor import (
    AbstractGithubExecutor,
)


MAX_WORKFLOW_POLL_ATTEMPTS = 10
WORKFLOW_POLL_DELAY_SECONDS = 2


class DispatchWorkflowExecutor(AbstractGithubExecutor):
    """
    Executor for dispatching GitHub workflow runs and tracking their execution.

    This executor implements the Port action for triggering GitHub Actions workflows.
    It supports:
    - Dispatching workflows with custom inputs
    - Tracking workflow execution status
    - Reporting workflow completion back to Port
    - Rate limit handling for GitHub API
    - Webhook processing for async status updates

    The executor uses workflow names as partition keys to ensure sequential
    execution of the same workflow, which is necessary for proper run tracking.
    It identifies workflow runs by finding the one closest to the trigger time
    and recording its ID.

    Attributes:
        ACTION_NAME (str): The name of this action in Port's spec ("dispatch_workflow")
        PARTITION_KEY (str): The key for partitioning runs ("workflow")
        WEBHOOK_PROCESSOR_CLASS (Type[AbstractWebhookProcessor]): Processor for workflow_run events
        WEBHOOK_PATH (str): Path for receiving GitHub webhook events
        _default_ref_cache (dict[str, str]): Cache of repository default branch names

    Example Usage in Port:
        ```yaml
        actions:
          dispatch_workflow:
            displayName: Trigger Workflow
            trigger: PORT
            inputs:
              repo:
                type: string
                description: Repository name
              workflow:
                type: string
                description: Workflow file name or ID
              workflowInputs:
                type: object
                description: Optional workflow inputs
        ```

    Example API Usage:
        ```python
        executor = DispatchWorkflowExecutor()
        await executor.execute(ActionRun(
            payload=IntegrationActionInvocationPayload(
                actionType="dispatch_workflow",
                integrationActionExecutionProperties={
                    "repo": "my-repo",
                    "workflow": "deploy.yml",
                    "workflowInputs": {"environment": "prod"}
                }
            )
        ))
        ```
    """

    ACTION_NAME = "dispatch_workflow"

    """
    We use the workflow name as the partition key because we track workflow executions
    by locating the workflow run closest to the trigger time and record its ID.
    Triggering the same workflow concurrently would prevent us from uniquely tracking each instance.
    """

    class DispatchWorkflowWebhookProcessor(BaseWorkflowRunWebhookProcessor):
        """
        Webhook processor for handling GitHub workflow run completion events.

        This processor is responsible for:
        1. Filtering workflow_run events to only process completed runs
        2. Verifying that the run was triggered by the authenticated user
        3. Updating the Port action run status based on the workflow conclusion
        4. Handling the mapping between GitHub run IDs and Port run IDs

        The processor only handles events where:
        - The event type is workflow_run
        - The workflow run status is "completed"
        - The actor matches the authenticated GitHub user
        - The run has a matching Port action run ID

        Attributes:
            Inherits all attributes from BaseWorkflowRunWebhookProcessor
        """

        @classmethod
        def get_processor_type(cls) -> WebhookProcessorType:
            return WebhookProcessorType.ACTION

        async def _should_process_event(self, event: WebhookEvent) -> bool:
            """
            Determine if this webhook event should be processed.
            """
            if super()._should_process_event(event):
                return False

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
            """
            Handle a workflow run completion webhook event.
            """
            workflow_run = payload["workflow_run"]

            external_id = build_external_id(workflow_run)
            action_run: ActionRun | None = (
                await ocean.port_client.get_run_by_external_id(external_id)
            )

            if (
                action_run
                and action_run.status == RunStatus.IN_PROGRESS
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

    async def _get_partition_key(self, run: ActionRun) -> str | None:
        """
        Get the workflow name as the partition key.
        """
        return run.payload.integrationActionExecutionProperties.get("workflow")

    async def _get_default_ref(self, organization: str, repo_name: str) -> str:
        """
        Get the default branch name for a repository, using cache when available.
        """
        key = f"{organization}:{repo_name}"
        if key in self._default_ref_cache:
            return self._default_ref_cache[key]

        repoExporter = RestRepositoryExporter(self.rest_client)
        repo = await repoExporter.get_resource(
            SingleRepositoryOptions(organization=organization, name=repo_name)
        )
        if not repo.get("default_branch"):
            raise Exception(f"Failed to get repository data for {repo_name}")

        self._default_ref_cache[key] = repo["default_branch"]
        return self._default_ref_cache[key]

    async def execute(self, run: ActionRun) -> None:
        """
        Execute a workflow dispatch action by triggering a GitHub Actions workflow.
        """
        organization = run.payload.integrationActionExecutionProperties.get("org")
        repo = run.payload.integrationActionExecutionProperties.get("repo")
        workflow = run.payload.integrationActionExecutionProperties.get("workflow")
        inputs = run.payload.integrationActionExecutionProperties.get(
            "workflowInputs", {}
        )

        if not (organization and repo and workflow):
            raise ValueError("repo and workflow are required")

        ref = await self._get_default_ref(organization, repo)
        try:
            isoDate = datetime.now(timezone.utc).isoformat()
            await self.rest_client.make_request(
                f"{self.rest_client.base_url}/repos/{organization}/{repo}/actions/workflows/{workflow}/dispatches",
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
                    f"{self.rest_client.base_url}/repos/{organization}/{repo}/actions/runs",
                    params={
                        "actor": authenticated_user.login,
                        "event": "workflow_dispatch",
                        "created": f">{isoDate}",
                        "exclude_pull_requests": True,
                        "branch": ref,
                    },
                    method="GET",
                    ignore_default_errors=False,
                )
                workflow_runs = response.get("workflow_runs", [])
                if len(workflow_runs) == 0:
                    logger.warning(
                        f"Couldn't find the triggered workflow run, waiting for {WORKFLOW_POLL_DELAY_SECONDS} seconds",
                        attempts_made=attempts_made,
                    )
                    await asyncio.sleep(WORKFLOW_POLL_DELAY_SECONDS)
                    attempts_made += 1

            if len(workflow_runs) == 0:
                raise Exception("No workflow runs found")

            workflow_run = workflow_runs[0]
            external_id = build_external_id(workflow_run)
            await ocean.port_client.patch_run(
                run.id, {"link": workflow_run["html_url"], "externalRunId": external_id}
            )
        except Exception as e:
            error_message = str(e)
            if isinstance(e, httpx.HTTPStatusError):
                error_message = json.loads(e.response.text).get("message", str(e))
            raise Exception(f"Error dispatching workflow: {error_message}")
