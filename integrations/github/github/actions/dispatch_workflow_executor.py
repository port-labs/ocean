import asyncio
from datetime import datetime, timezone
import json
from typing import Any

import httpx
from loguru import logger
from github.actions.utils import build_external_id
from github.context.auth import (
    get_authenticated_actor,
)
from github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)
from github.core.options import SingleRepositoryOptions
from github.webhook.registry import (
    WEBHOOK_PATH as DISPATCH_WEBHOOK_PATH,
)
from github.helpers.exceptions import (
    InvalidActionParametersException,
    NoWorkflowRunsFoundException,
    RepositoryDefaultBranchNotFoundException,
)
from github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor import (
    DispatchWorkflowWebhookProcessor,
)
from port_ocean.context.ocean import ocean

from port_ocean.core.models import (
    ActionRun,
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
            logger.info(
                f"Using cached default branch for {organization}/{repo_name}: {self._default_ref_cache[key]}",
                organization=organization,
                repo_name=repo_name,
                branch=self._default_ref_cache[key],
            )
            return self._default_ref_cache[key]

        repoExporter = RestRepositoryExporter(self.rest_client)
        repo = await repoExporter.get_resource(
            SingleRepositoryOptions(organization=organization, name=repo_name)
        )
        if not repo.get("default_branch"):
            logger.error(
                f"Default branch not found for repository {organization}/{repo_name}",
                organization=organization,
                repo_name=repo_name,
            )
            raise RepositoryDefaultBranchNotFoundException(
                f"Default branch not found for repository {organization}/{repo_name}"
            )

        logger.info(
            f"Fetched default branch for {organization}/{repo_name}: {repo['default_branch']}",
            organization=organization,
            repo_name=repo_name,
            branch=repo["default_branch"],
        )
        self._default_ref_cache[key] = repo["default_branch"]
        return self._default_ref_cache[key]

    async def _get_workflow_run(
        self, organization: str, repo: str, ref: str, isoDate: str
    ) -> dict[str, Any]:
        """
        Get the workflow run for a given workflow.
        """
        workflow_runs: list[dict[str, Any]] = []
        actor = await get_authenticated_actor()
        attempts_made = 0
        while len(workflow_runs) == 0 and attempts_made < MAX_WORKFLOW_POLL_ATTEMPTS:
            response = await self.rest_client.send_api_request(
                f"{self.rest_client.base_url}/repos/{organization}/{repo}/actions/runs",
                params={
                    "actor": actor,
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
            raise NoWorkflowRunsFoundException("No workflow runs found")

        logger.info(
            f"Found workflow run for {organization}/{repo} with ref {ref}: {workflow_runs[0]['id']}",
        )
        return workflow_runs[0]

    async def execute(self, run: ActionRun) -> None:
        """
        Execute a workflow dispatch action by triggering a GitHub Actions workflow.
        """
        logger.info(f"Dispatching workflow for action run {run.id}", run_id=run.id)
        organization = run.payload.integrationActionExecutionProperties.get("org")
        repo = run.payload.integrationActionExecutionProperties.get("repo")
        workflow = run.payload.integrationActionExecutionProperties.get("workflow")
        inputs = run.payload.integrationActionExecutionProperties.get(
            "workflowInputs", {}
        )

        if not (organization and repo and workflow):
            raise InvalidActionParametersException(
                "organization, repo and workflow are required"
            )

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

            workflow_run = await self._get_workflow_run(
                organization, repo, ref, isoDate
            )
            external_id = build_external_id(workflow_run)
            await ocean.port_client.patch_run(
                run.id, {"link": workflow_run["html_url"], "externalRunId": external_id}
            )
        except Exception as e:
            error_message = str(e)
            if isinstance(e, httpx.HTTPStatusError):
                error_message = json.loads(e.response.text).get("message", str(e))
            raise Exception(f"Error dispatching workflow: {error_message}")
