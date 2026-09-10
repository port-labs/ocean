from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from azure_devops.actions.abstract_ado_executor import AbstractAzureDevopsExecutor
from azure_devops.actions.exceptions import (
    CreatePullRequestError,
    InvalidActionParametersError,
)
from azure_devops.client.azure_devops_client import CreatePullRequestOptions
from azure_devops.misc import extract_org_name_from_url
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun


class CreatePullRequestInputs(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    organization: str = Field(min_length=1)
    project: str = Field(min_length=1)
    repositoryId: str = Field(min_length=1)
    title: str = Field(min_length=1)
    sourceRefName: str = Field(min_length=1)
    targetRefName: str = Field(min_length=1)
    description: str | None = None


def _parse_create_pull_request_inputs(
    execution_properties: dict[str, Any],
) -> CreatePullRequestInputs:
    try:
        return CreatePullRequestInputs.model_validate(execution_properties)
    except ValidationError as error:
        messages = [
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
            for err in error.errors()
        ]
        raise ValueError("; ".join(messages)) from error


class CreatePullRequestExecutor(AbstractAzureDevopsExecutor):
    """Executor for creating Azure DevOps pull requests."""

    ACTION_NAME = "create_pull_request"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        organization = run.execution_properties.get("organization")
        project = run.execution_properties.get("project")
        repository_id = run.execution_properties.get("repositoryId")
        if not (organization and project and repository_id):
            return None
        return f"{organization}/{project}/{repository_id}"

    async def execute(self, run: IntegrationRun) -> None:
        try:
            inputs = _parse_create_pull_request_inputs(run.execution_properties)
        except ValueError as error:
            logger.warning(
                f"Invalid parameters for action run {run.id}",
                run_id=run.id,
                error=str(error),
            )
            raise InvalidActionParametersError(str(error)) from error

        configured_org = extract_org_name_from_url(self.client._organization_base_url)
        if inputs.organization.lower() != configured_org.lower():
            raise InvalidActionParametersError(
                f"Organization '{inputs.organization}' does not match the configured "
                f"organization '{configured_org}'"
            )

        options = CreatePullRequestOptions(
            title=inputs.title,
            source_ref_name=inputs.sourceRefName,
            target_ref_name=inputs.targetRefName,
            description=inputs.description or None,
        )

        logger.info(
            f"Creating pull request '{inputs.title}' in repository "
            f"{inputs.repositoryId} for action run {run.id}",
            run_id=run.id,
            project_id=inputs.project,
            repository_id=inputs.repositoryId,
        )
        await ocean.port_client.post_run_log(
            run,
            f"Creating pull request '{inputs.title}' in repository "
            f"{inputs.repositoryId}",
            should_raise=False,
        )

        try:
            pull_request = await self.client.create_pull_request(
                inputs.project,
                inputs.repositoryId,
                options,
            )
        except httpx.HTTPStatusError as error:
            logger.error(
                f"Azure DevOps rejected pull request creation for action run {run.id}: "
                f"HTTP {error.response.status_code}",
                run_id=run.id,
                project_id=inputs.project,
                repository_id=inputs.repositoryId,
                status_code=error.response.status_code,
            )
            raise CreatePullRequestError.from_response(
                error.response,
                f"Could not create pull request in repository '{inputs.repositoryId}'",
            )

        pull_request_id = pull_request.get("pullRequestId")
        if pull_request_id is None:
            raise CreatePullRequestError(
                "Failed to create pull request: upstream returned an empty or "
                "incomplete response"
            )

        web_link = pull_request.get("_links", {}).get("web", {}).get("href", "")
        message = (
            f"Pull request #{pull_request_id} created: {web_link}"
            if web_link
            else f"Pull request #{pull_request_id} created"
        )
        await ocean.port_client.post_run_log(run, message, should_raise=False)
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
        )
