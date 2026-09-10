import httpx
from loguru import logger
from pydantic import Field

from azure_devops.actions.abstract_ado_action_input import (
    AbstractAzureDevopsActionInput,
)
from azure_devops.actions.abstract_ado_executor import AbstractAzureDevopsExecutor
from azure_devops.actions.exceptions import (
    InvalidActionParametersError,
    MergePullRequestError,
)
from azure_devops.misc import extract_org_name_from_url
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun


class MergePullRequestInputs(AbstractAzureDevopsActionInput):
    organization: str = Field(min_length=1)
    project: str = Field(min_length=1)
    repositoryId: str = Field(min_length=1)
    pullRequestId: str = Field(min_length=1)


class MergePullRequestExecutor(AbstractAzureDevopsExecutor):
    """Executor for merging Azure DevOps pull requests."""

    ACTION_NAME = "merge_pull_request"
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
            inputs = MergePullRequestInputs.from_execution_properties(
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
            f"Merging pull request {inputs.pullRequestId} in repository "
            f"{inputs.repositoryId} for action run {run.id}",
            run_id=run.id,
            project_id=inputs.project,
            repository_id=inputs.repositoryId,
            pull_request_id=inputs.pullRequestId,
        )
        await ocean.port_client.post_run_log(
            run,
            f"Merging pull request {inputs.pullRequestId} in repository "
            f"{inputs.repositoryId}",
            should_raise=False,
        )

        try:
            pull_request = await self.client.merge_pull_request(
                inputs.project,
                inputs.repositoryId,
                inputs.pullRequestId,
            )
        except httpx.HTTPStatusError as error:
            logger.error(
                f"Azure DevOps rejected pull request merge for action run {run.id}: "
                f"HTTP {error.response.status_code}",
                run_id=run.id,
                project_id=inputs.project,
                repository_id=inputs.repositoryId,
                pull_request_id=inputs.pullRequestId,
                status_code=error.response.status_code,
            )
            raise MergePullRequestError.from_response(
                error.response,
                f"Could not merge pull request '{inputs.pullRequestId}' in repository "
                f"'{inputs.repositoryId}'",
            )
        except RuntimeError as error:
            raise MergePullRequestError(str(error)) from error

        merged_id = pull_request.get("pullRequestId")
        if merged_id is None:
            raise MergePullRequestError(
                "Failed to merge pull request: upstream returned an empty or "
                "incomplete response"
            )

        web_link = pull_request.get("_links", {}).get("web", {}).get("href", "")
        message = (
            f"Pull request #{merged_id} merged: {web_link}"
            if web_link
            else f"Pull request #{merged_id} merged"
        )
        await ocean.port_client.post_run_log(run, message, should_raise=False)
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
        )
