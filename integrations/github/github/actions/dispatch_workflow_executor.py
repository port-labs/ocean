import asyncio
from datetime import datetime, timezone
import json
from typing import Any

import httpx
from loguru import logger
from github.actions.utils import build_external_id
from github.clients.auth import get_auth_provider
from github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)
from github.core.options import SingleRepositoryOptions, SingleWorkflowRunOptions
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
from github.core.exporters.workflow_runs_exporter import RestWorkflowRunExporter
from port_ocean.context.ocean import ocean

from port_ocean.core.models import IntegrationRun
from github.actions.abstract_github_executor import (
    AbstractGithubExecutor,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError


MAX_WORKFLOW_POLL_ATTEMPTS = 30
WORKFLOW_POLL_DELAY_SECONDS = 2


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

    By default, GitHub returns a workflow run ID when `return_run_details` is set.
    The executor fetches that run and builds a unique external ID from it, so
    multiple dispatches of the same workflow can run concurrently without collision.

    When `legacyDispatchWorkflowTracking` is enabled (for GitHub Enterprise Server
    versions older than 3.21 that do not support `return_run_details` on workflow
    dispatch), the executor polls GitHub for the dispatched workflow run and uses
    `{organization}/{repo}/{workflow}` as the partition key to serialize dispatches
    of the same workflow.

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

    def _use_legacy_dispatch_workflow_tracking(self) -> bool:
        return bool(
            ocean.integration_config.get("legacy_dispatch_workflow_tracking", False)
        )

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        if not self._use_legacy_dispatch_workflow_tracking():
            return None

        organization = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        workflow = run.execution_properties.get("workflow")
        if not (organization and repo and workflow):
            return None

        return f"{organization}/{repo}/{workflow}"

    async def _get_default_ref(self, organization: str, repo_name: str) -> str:
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

    async def _get_workflow_run(
        self, organization: str, repo: str, workflow: str, ref: str, iso_date: str
    ) -> dict[str, Any]:
        workflow_runs: list[dict[str, Any]] = []
        actor = await get_auth_provider().get_integration_actor()
        attempts_made = 0
        while len(workflow_runs) == 0 and attempts_made < MAX_WORKFLOW_POLL_ATTEMPTS:
            response = await self.rest_client.send_api_request(
                f"{self.rest_client.base_url}/repos/{organization}/{repo}/actions/workflows/{workflow}/runs",
                params={
                    "actor": actor,
                    "event": "workflow_dispatch",
                    "created": f">={iso_date}",
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
            raise NoWorkflowRunsFoundException(
                "Workflow dispatched successfully but due to a delay in GitHub we were unable to track it's progress"
            )

        logger.info(
            f"Found workflow run for {organization}/{repo} with ref {ref}: {workflow_runs[0]['id']}",
        )
        return workflow_runs[0]

    def _parse_inputs(self, raw_inputs: dict[str, Any]) -> dict[str, Any]:
        inputs: dict[str, str] = {}
        for key, value in raw_inputs.items():
            if isinstance(value, str):
                inputs[key] = value
            else:
                inputs[key] = json.dumps(value)
        return inputs

    async def _dispatch_workflow_legacy(
        self,
        organization: str,
        repo: str,
        workflow: str,
        ref: str,
        inputs: dict[str, str],
    ) -> None:
        await self.rest_client.make_request(
            f"{self.rest_client.base_url}/repos/{organization}/{repo}/actions/workflows/{workflow}/dispatches",
            method="POST",
            json_data={
                "ref": ref,
                "inputs": inputs,
            },
            ignore_default_errors=False,
        )

    async def _dispatch_workflow(
        self,
        organization: str,
        repo: str,
        workflow: str,
        ref: str,
        inputs: dict[str, str],
    ) -> dict[str, Any]:
        dispatch_payload: dict[str, Any] = {
            "ref": ref,
            "inputs": inputs,
            "return_run_details": True,
        }

        response = await self.rest_client.make_request(
            f"{self.rest_client.base_url}/repos/{organization}/{repo}/actions/workflows/{workflow}/dispatches",
            method="POST",
            json_data=dispatch_payload,
            ignore_default_errors=False,
        )
        return response.json()

    async def execute(self, run: IntegrationRun) -> None:
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
            if self._use_legacy_dispatch_workflow_tracking():
                iso_date = datetime.now(timezone.utc).isoformat()
                await self._dispatch_workflow_legacy(
                    organization, repo, workflow, ref, inputs
                )
                workflow_run = await self._get_workflow_run(
                    organization, repo, workflow, ref, iso_date
                )
                workflow_run_id = workflow_run["id"]
            else:
                dispatch_response = await self._dispatch_workflow(
                    organization, repo, workflow, ref, inputs
                )
                workflow_run_id = dispatch_response.get("workflow_run_id")
                if not workflow_run_id:
                    raise ActionExecutionError("Workflow run ID not found")

                fetched_workflow_run = await self._workflow_run_exporter.get_resource(
                    SingleWorkflowRunOptions(
                        organization=organization,
                        repo_name=repo,
                        run_id=workflow_run_id,
                    )
                )
                if not fetched_workflow_run:
                    raise ActionExecutionError(
                        f"Workflow run {workflow_run_id} not found in {organization}/{repo}"
                    )
                workflow_run = fetched_workflow_run

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
