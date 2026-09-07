import httpx
from loguru import logger

from azure_devops.actions.abstract_ado_executor import AbstractAzureDevopsExecutor
from azure_devops.actions.exceptions import (
    ClosePullRequestError,
    InvalidActionParametersError,
)
from azure_devops.misc import extract_org_name_from_url
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun


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
        organization = run.execution_properties.get("organization")
        project_input = run.execution_properties.get("project")
        repository_id = run.execution_properties.get("repositoryId")
        pull_request_id = run.execution_properties.get("pullRequestId")

        missing = [
            name
            for name, value in [
                ("organization", organization),
                ("project", project_input),
                ("repositoryId", repository_id),
                ("pullRequestId", pull_request_id),
            ]
            if not value
        ]
        if missing:
            logger.warning(
                f"Missing required parameters for action run {run.id}",
                run_id=run.id,
                missing=missing,
            )
            raise InvalidActionParametersError(
                f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required"
            )

        configured_org = extract_org_name_from_url(self.client._organization_base_url)
        if str(organization).lower() != configured_org.lower():
            raise InvalidActionParametersError(
                f"Organization '{organization}' does not match the configured "
                f"organization '{configured_org}'"
            )

        project = await self.client.get_single_project(str(project_input))
        if not project:
            logger.warning(
                f"Project '{project_input}' was not found for action run {run.id}",
                run_id=run.id,
                project=project_input,
            )
            raise InvalidActionParametersError(
                f"Project '{project_input}' was not found"
            )
        project_id = project["id"]

        logger.info(
            f"Closing pull request {pull_request_id} in repository {repository_id} "
            f"for action run {run.id}",
            run_id=run.id,
            project_id=project_id,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
        )
        await ocean.port_client.post_run_log(
            run,
            f"Closing pull request {pull_request_id} in repository {repository_id}",
            should_raise=False,
        )

        try:
            pull_request = await self.client.close_pull_request(
                project_id, str(repository_id), str(pull_request_id)
            )
        except httpx.HTTPStatusError as error:
            logger.error(
                f"Azure DevOps rejected pull request close for action run {run.id}: "
                f"HTTP {error.response.status_code}",
                run_id=run.id,
                project_id=project_id,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                status_code=error.response.status_code,
            )
            raise ClosePullRequestError.from_response(
                error.response,
                f"Could not close pull request '{pull_request_id}' in repository "
                f"'{repository_id}'",
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
