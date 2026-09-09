import httpx
from loguru import logger
from pydantic import Field

from azure_devops.actions.abstract_ado_action_input import AbstractAzureDevopsActionInput
from azure_devops.actions.abstract_ado_executor import AbstractAzureDevopsExecutor
from azure_devops.actions.exceptions import (
    ClosePullRequestError,
    InvalidActionParametersError,
)
from azure_devops.misc import extract_org_name_from_url
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun


class ClosePullRequestInputs(AbstractAzureDevopsActionInput):
    organization: str = Field(min_length=1)
    project: str = Field(min_length=1)
    repositoryId: str = Field(min_length=1)
    pullRequestId: str = Field(min_length=1)


class ClosePullRequestExecutor(AbstractAzureDevopsExecutor):
    """Executor for abandoning Azure DevOps pull requests."""

    ACTION_NAME = "close_pull_request"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        organization = run.execution_properties.get("organization")
        project = run.execution_properties.get("project")
        repository_id = run.execution_properties.get("repositoryId")
        pull_request_id = run.execution_properties.get("pullRequestId")
        if not (organization and project and repository_id and pull_request_id):
            return None
        return f"{organization}/{project}/{repository_id}/{pull_request_id}"

    async def execute(self, run: IntegrationRun) -> None:
        try:
            inputs = ClosePullRequestInputs.from_execution_properties(
                run.execution_properties
            )
        except InvalidActionParametersError as error:
            logger.warning(
                f"Invalid parameters for action run {run.id}",
                run_id=run.id,
                error=str(error),
            )
            raise

        configured_org = extract_org_name_from_url(self.client._organization_base_url)
        if inputs.organization.lower() != configured_org.lower():
            raise InvalidActionParametersError(
                f"Organization '{inputs.organization}' does not match the configured "
                f"organization '{configured_org}'"
            )

        logger.info(
            f"Closing pull request {inputs.pullRequestId} in repository "
            f"{inputs.repositoryId} for action run {run.id}",
            run_id=run.id,
            project_id=inputs.project,
            repository_id=inputs.repositoryId,
            pull_request_id=inputs.pullRequestId,
        )
        await ocean.port_client.post_run_log(
            run,
            f"Closing pull request {inputs.pullRequestId} in repository "
            f"{inputs.repositoryId}",
            should_raise=False,
        )

        try:
            pull_request = await self.client.close_pull_request(
                inputs.project,
                inputs.repositoryId,
                inputs.pullRequestId,
            )
        except httpx.HTTPStatusError as error:
            logger.error(
                f"Azure DevOps rejected pull request close for action run {run.id}: "
                f"HTTP {error.response.status_code}",
                run_id=run.id,
                project_id=inputs.project,
                repository_id=inputs.repositoryId,
                pull_request_id=inputs.pullRequestId,
                status_code=error.response.status_code,
            )
            raise ClosePullRequestError.from_response(
                error.response,
                f"Could not close pull request '{inputs.pullRequestId}' in repository "
                f"'{inputs.repositoryId}'",
            )

        closed_id = pull_request.get("pullRequestId")
        if closed_id is None:
            raise ClosePullRequestError(
                "Failed to close pull request: upstream returned an empty or "
                "incomplete response"
            )

        web_link = pull_request.get("_links", {}).get("web", {}).get("href", "")
        message = (
            f"Pull request #{closed_id} closed: {web_link}"
            if web_link
            else f"Pull request #{closed_id} closed"
        )
        await ocean.port_client.post_run_log(run, message, should_raise=False)
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
        )
