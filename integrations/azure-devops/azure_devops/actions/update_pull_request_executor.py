from typing import Any, Optional, Sequence

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from azure_devops.actions.abstract_ado_executor import AbstractAzureDevopsExecutor
from azure_devops.actions.exceptions import (
    InvalidActionParametersError,
    UpdatePullRequestError,
)
from azure_devops.client.azure_devops_client import UpdatePullRequestOptions

COMPLETED_STATUS = "completed"
# The API also defines "notSet" and "all", but neither is meaningful on an update:
# "all" only applies to search criteria and "notSet" is the default state.
VALID_STATUSES = ("active", "abandoned", COMPLETED_STATUS)
VALID_MERGE_STRATEGIES = ("noFastForward", "squash", "rebase", "rebaseMerge")
MAX_DESCRIPTION_LENGTH = 4000


def _normalize_choice(
    value: Any, allowed: Sequence[str], field_name: str
) -> Optional[str]:
    """Match a user-supplied value against the API's casing, or reject it."""
    if value is None or value == "":
        return None
    for candidate in allowed:
        if str(value).lower() == candidate.lower():
            return candidate
    raise InvalidActionParametersError(
        f"Invalid {field_name} '{value}'. Allowed values are: {', '.join(allowed)}"
    )


class UpdatePullRequestExecutor(AbstractAzureDevopsExecutor):
    """Executor for updating an Azure DevOps pull request.

    Azure DevOps' Update Pull Request API applies the change and returns the
    updated pull request in the same call, so the run is completed here rather
    than waiting for a service hook.
    """

    ACTION_NAME = "update_pull_request"

    async def execute(self, run: IntegrationRun) -> None:
        logger.info(f"Updating pull request for action run {run.id}", run_id=run.id)
        properties = run.execution_properties
        project_input = properties.get("project")
        repository = properties.get("repository")
        pull_request_id = properties.get("pullRequestId")
        if not (project_input and repository and pull_request_id):
            logger.warning(
                f"Missing required parameters for action run {run.id}",
                run_id=run.id,
                project=project_input,
                repository=repository,
                pull_request_id=pull_request_id,
            )
            raise InvalidActionParametersError(
                "project, repository and pullRequestId are required"
            )

        description = properties.get("description")
        if description is not None and len(str(description)) > MAX_DESCRIPTION_LENGTH:
            logger.warning(
                f"Description exceeds the maximum length for action run {run.id}",
                run_id=run.id,
                description_length=len(str(description)),
            )
            raise InvalidActionParametersError(
                f"description must be at most {MAX_DESCRIPTION_LENGTH} characters, "
                f"got {len(str(description))}"
            )

        options = UpdatePullRequestOptions(
            title=properties.get("title"),
            description=description,
            status=_normalize_choice(
                properties.get("status"), VALID_STATUSES, "status"
            ),
            target_branch=properties.get("targetBranch"),
            merge_strategy=_normalize_choice(
                properties.get("mergeStrategy"),
                VALID_MERGE_STRATEGIES,
                "mergeStrategy",
            ),
            delete_source_branch=properties.get("deleteSourceBranch"),
            merge_commit_message=properties.get("mergeCommitMessage"),
        )
        if not self._has_updates(options):
            logger.warning(
                f"No fields to update were provided for action run {run.id}",
                run_id=run.id,
                pull_request_id=pull_request_id,
            )
            raise InvalidActionParametersError(
                "At least one field to update is required: title, description, status, "
                "targetBranch, mergeStrategy, deleteSourceBranch or mergeCommitMessage"
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
        repository_id = await self._resolve_repository_id(
            run, str(project_id), str(repository)
        )

        await ocean.port_client.post_run_log(
            run,
            f"Updating pull request {pull_request_id} in repository '{repository}'",
            status_label="Updating",
        )

        if options.status == COMPLETED_STATUS:
            options.last_merge_source_commit = (
                await self._resolve_last_merge_source_commit(str(pull_request_id))
            )

        try:
            pull_request = await self.client.update_pull_request(
                project_id, repository_id, str(pull_request_id), options
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Azure DevOps rejected the update of pull request {pull_request_id} "
                f"for action run {run.id}: HTTP {e.response.status_code}",
                run_id=run.id,
                project_id=project_id,
                repository=repository,
                pull_request_id=pull_request_id,
                status_code=e.response.status_code,
            )
            raise UpdatePullRequestError.from_response(
                e.response,
                f"Error updating pull request {pull_request_id} in repository '{repository}'",
            )

        if not pull_request or "pullRequestId" not in pull_request:
            logger.error(
                f"Azure DevOps returned an unexpected response while updating pull "
                f"request {pull_request_id} for action run {run.id}",
                run_id=run.id,
                pull_request_id=pull_request_id,
            )
            raise UpdatePullRequestError(
                f"Azure DevOps returned an unexpected response while updating pull "
                f"request {pull_request_id}"
            )

        updated_status = pull_request.get("status", "unknown")
        link = pull_request.get("_links", {}).get("web", {}).get("href", "")
        logger.info(
            f"Pull request {pull_request_id} updated for action run {run.id}",
            run_id=run.id,
            pull_request_id=pull_request_id,
            status=updated_status,
            link=link,
        )
        message = (
            f"Pull request {pull_request_id} updated, its status is now "
            f"'{updated_status}'"
        )
        if link:
            message = f"{message}: {link}"
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Updated",
        )

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        properties = run.execution_properties
        project = properties.get("project")
        repository = properties.get("repository")
        pull_request_id = properties.get("pullRequestId")
        if not (project and repository and pull_request_id):
            return None
        return f"{project}/{repository}/{pull_request_id}"

    @staticmethod
    def _has_updates(options: UpdatePullRequestOptions) -> bool:
        return any(
            value is not None
            for value in (
                options.title,
                options.description,
                options.status,
                options.target_branch,
                options.merge_strategy,
                options.delete_source_branch,
                options.merge_commit_message,
            )
        )

    async def _resolve_repository_id(
        self, run: IntegrationRun, project_id: str, repository: str
    ) -> str:
        """Resolve a repository name or ID to the ID the update route expects.

        The endpoint is keyed by the repository ID of the pull request's target
        branch, and this lookup accepts either form, so a user can supply the
        name they see in Azure DevOps.
        """
        found = await self.client.get_repository_by_name(project_id, repository)
        if not found or not found.get("id"):
            logger.warning(
                f"Repository '{repository}' was not found for action run {run.id}",
                run_id=run.id,
                project_id=project_id,
                repository=repository,
            )
            raise InvalidActionParametersError(
                f"Repository '{repository}' was not found"
            )
        return str(found["id"])

    async def _resolve_last_merge_source_commit(
        self, pull_request_id: str
    ) -> dict[str, Any]:
        """Fetch the source commit that completing the pull request must merge.

        Azure DevOps requires it so the merge runs against the source version
        the caller last saw, and rejects the completion otherwise.
        """
        pull_request = await self.client.get_pull_request(pull_request_id)
        if not pull_request:
            raise InvalidActionParametersError(
                f"Pull request {pull_request_id} was not found"
            )
        commit_id = (pull_request.get("lastMergeSourceCommit") or {}).get("commitId")
        if not commit_id:
            raise UpdatePullRequestError(
                f"Pull request {pull_request_id} cannot be completed: Azure DevOps has "
                "not published a merge commit for its source branch yet"
            )
        return {"commitId": commit_id}
