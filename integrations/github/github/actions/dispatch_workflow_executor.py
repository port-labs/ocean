import json
from typing import Any

import httpx
from loguru import logger
from github.actions.utils import build_external_id
from github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)
from github.core.options import SingleRepositoryOptions, SingleWorkflowRunOptions
from github.webhook.registry import (
    WEBHOOK_PATH as DISPATCH_WEBHOOK_PATH,
)
from github.helpers.exceptions import (
    InvalidActionParametersException,
    RepositoryDefaultBranchNotFoundException,
)
from github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor import (
    DispatchWorkflowWebhookProcessor,
)
from github.core.exporters.workflow_runs_exporter import RestWorkflowRunExporter
from port_ocean.context.ocean import ocean

from port_ocean.core.models import ActionRun, WorkflowNodeRun
from github.actions.abstract_github_executor import (
    AbstractGithubExecutor,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError


class DispatchWorkflowExecutor(AbstractGithubExecutor):
    """
    Executor for dispatching GitHub workflow runs and tracking their execution.

    This executor implements the Port action for triggering GitHub Actions workflows.
    It supports:
    - Dispatching workflows with custom inputs
    - Tracking workflow execution status via the returned workflow run ID
    - Reporting workflow completion back to Port
    - Rate limit handling for GitHub API
    - Webhook processing for async status updates

    On dispatch, GitHub returns a workflow run ID when `return_run_details` is set.
    The executor fetches that run and builds a unique external ID from it, so
    multiple dispatches of the same workflow can run concurrently without collision.

    Attributes:
        ACTION_NAME (str): The name of this action in Port's spec ("dispatch_workflow")
        WEBHOOK_PROCESSOR_CLASS (Type[AbstractWebhookProcessor]): Processor for workflow_run events
        WEBHOOK_PATH (str): Path for receiving GitHub webhook events
        _default_ref_cache (dict[str, str]): Cache of repository default branch names
        _workflow_run_exporter (RestWorkflowRunExporter): Fetches dispatched workflow runs by ID

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

    WEBHOOK_PROCESSOR_CLASS = DispatchWorkflowWebhookProcessor
    WEBHOOK_PATH = DISPATCH_WEBHOOK_PATH
    _default_ref_cache: dict[str, str] = {}

    def __init__(self) -> None:
        super().__init__()
        self._workflow_run_exporter = RestWorkflowRunExporter(self.rest_client)

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
        if not repo or not repo.get("default_branch"):
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

    def _parse_inputs(self, raw_inputs: dict[str, Any]) -> dict[str, Any]:
        inputs: dict[str, str] = {}
        for key, value in raw_inputs.items():
            if isinstance(value, str):
                inputs[key] = value
            else:
                inputs[key] = json.dumps(value)
        return inputs

    async def execute(self, run: ActionRun | WorkflowNodeRun) -> None:
        """
        Dispatch a GitHub Actions workflow and register the returned run with Port.

        Requests `return_run_details` from GitHub, fetches the workflow run by ID,
        and calls `update_run_started` with its URL and external ID.
        """
        logger.info(f"Dispatching workflow for action run {run.id}", run_id=run.id)
        organization = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        workflow = run.execution_properties.get("workflow")

        if not (organization and repo and workflow):
            raise InvalidActionParametersException(
                "organization, repo and workflow are required"
            )

        inputs: dict[str, str] = self._parse_inputs(
            run.execution_properties.get("workflowInputs", {})
        )
        ref = inputs.pop("ref", None)
        if not ref:
            ref = await self._get_default_ref(organization, repo)
        try:
            response = await self.rest_client.make_request(
                f"{self.rest_client.base_url}/repos/{organization}/{repo}/actions/workflows/{workflow}/dispatches",
                method="POST",
                json_data={
                    "ref": ref,
                    "inputs": inputs,
                    "return_run_details": True,
                },
                ignore_default_errors=False,
            )
            workflow_run_id = response.json().get("workflow_run_id")
            if not workflow_run_id:
                raise ActionExecutionError("Workflow run ID not found")

            workflow_run = await self._workflow_run_exporter.get_resource(
                SingleWorkflowRunOptions(
                    organization=organization,
                    repo_name=repo,
                    run_id=workflow_run_id,
                )
            )
            if not workflow_run:
                raise ActionExecutionError(
                    f"Workflow run {workflow_run_id} not found in {organization}/{repo}"
                )
            external_id = build_external_id(workflow_run)

            await ocean.port_client.update_run_started(
                run,
                workflow_run["html_url"],
                external_id,
                extra_output={"workflowRunId": workflow_run_id},
            )
        except Exception as e:
            error_message = str(e)
            if isinstance(e, httpx.HTTPStatusError):
                error_message = json.loads(e.response.text).get("message", str(e))
            raise ActionExecutionError(f"Error dispatching workflow: {error_message}")
