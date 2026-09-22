import httpx
from loguru import logger
from pydantic import Field

from azure_devops.actions.abstract_ado_action_input import (
    AbstractAzureDevopsActionInput,
)
from azure_devops.actions.abstract_ado_executor import AbstractAzureDevopsExecutor
from azure_devops.actions.exceptions import (
    InvalidActionParametersError,
    UpdatePullRequestLabelsError,
)
from azure_devops.misc import extract_org_name_from_url
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun


class UpdatePullRequestLabelsInputs(AbstractAzureDevopsActionInput):
    organization: str = Field(min_length=1)
    project: str = Field(min_length=1)
    repositoryId: str = Field(min_length=1)
    pullRequestId: str = Field(min_length=1)
    label: str = Field(min_length=1)


class UpdatePullRequestLabelsExecutor(AbstractAzureDevopsExecutor):
    """Executor for adding a label to an Azure DevOps pull request.

    Azure DevOps creates pull request labels one at a time, so each run adds a
    single label and the run is completed here rather than waiting for a
    service hook.
    """

    ACTION_NAME = "update_pull_request_labels"
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
            inputs = UpdatePullRequestLabelsInputs.from_execution_properties(
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
            f"Adding label '{inputs.label}' to pull request {inputs.pullRequestId} in "
            f"repository {inputs.repositoryId} for action run {run.id}",
            run_id=run.id,
            project_id=inputs.project,
            repository_id=inputs.repositoryId,
            pull_request_id=inputs.pullRequestId,
        )
        await ocean.port_client.post_run_log(
            run,
            f"Adding label '{inputs.label}' to pull request {inputs.pullRequestId} in "
            f"repository {inputs.repositoryId}",
            should_raise=False,
        )

        try:
            created_label = await self.client.create_pull_request_label(
                inputs.project,
                inputs.repositoryId,
                inputs.pullRequestId,
                inputs.label,
            )
        except httpx.HTTPStatusError as error:
            logger.error(
                f"Azure DevOps rejected the label on pull request "
                f"{inputs.pullRequestId} for action run {run.id}: "
                f"HTTP {error.response.status_code}",
                run_id=run.id,
                project_id=inputs.project,
                repository_id=inputs.repositoryId,
                pull_request_id=inputs.pullRequestId,
                status_code=error.response.status_code,
            )
            raise UpdatePullRequestLabelsError.from_response(
                error.response,
                f"Could not add label '{inputs.label}' to pull request "
                f"'{inputs.pullRequestId}' in repository '{inputs.repositoryId}'",
            )

        if not created_label or "name" not in created_label:
            raise UpdatePullRequestLabelsError(
                f"Failed to add label '{inputs.label}' to pull request "
                f"{inputs.pullRequestId}: upstream returned an empty or incomplete "
                "response"
            )

        message = (
            f"Label '{created_label['name']}' added to pull request "
            f"{inputs.pullRequestId}"
        )
        await ocean.port_client.post_run_log(run, message, should_raise=False)
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
        )
