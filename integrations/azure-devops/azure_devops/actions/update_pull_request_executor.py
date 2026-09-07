from typing import Any, Optional, Sequence

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from azure_devops.actions.abstract_ado_executor import AbstractAzureDevopsExecutor
from azure_devops.actions.exceptions import (
    InvalidActionParametersError,
    UpdatePullRequestError,
)

COMPLETED_STATUS = "completed"
# The API also defines "notSet" and "all", but neither is meaningful on an update:
# "all" only applies to search criteria and "notSet" is the default state.
VALID_STATUSES = ("active", "abandoned", COMPLETED_STATUS)
VALID_MERGE_STRATEGIES = ("noFastForward", "squash", "rebase", "rebaseMerge")
MAX_DESCRIPTION_LENGTH = 4000
UPDATE_FIELD_NAMES = (
    "title",
    "description",
    "status",
    "targetBranch",
    "mergeStrategy",
    "deleteSourceBranch",
    "mergeCommitMessage",
    "bypassPolicy",
    "bypassReason",
    "transitionWorkItems",
    "autoCompleteIgnoreConfigIds",
    "disableRenames",
    "conflictAuthorshipCommits",
    "detectRenameFalsePositives",
    "autoCompleteSetById",
)


class UpdatePullRequestInputs(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    project: str = Field(min_length=1)
    repositoryId: str = Field(min_length=1)
    pullRequestId: str = Field(min_length=1)
    title: str | None = None
    description: str | None = None
    status: str | None = None
    targetBranch: str | None = None
    mergeStrategy: str | None = None
    deleteSourceBranch: bool | None = None
    mergeCommitMessage: str | None = None
    bypassPolicy: bool | None = None
    bypassReason: str | None = None
    transitionWorkItems: bool | None = None
    autoCompleteIgnoreConfigIds: str | None = None
    disableRenames: bool | None = None
    conflictAuthorshipCommits: bool | None = None
    detectRenameFalsePositives: bool | None = None
    autoCompleteSetById: str | None = None


def _parse_update_pull_request_inputs(
    execution_properties: dict[str, Any],
) -> UpdatePullRequestInputs:
    try:
        return UpdatePullRequestInputs.model_validate(execution_properties)
    except ValidationError as error:
        messages = [
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
            for err in error.errors()
        ]
        raise ValueError("; ".join(messages)) from error


OPTIONAL_STRING_FIELDS = (
    "title",
    "description",
    "status",
    "targetBranch",
    "mergeStrategy",
    "mergeCommitMessage",
    "bypassReason",
    "autoCompleteIgnoreConfigIds",
    "autoCompleteSetById",
)


def _blank_to_none(value: str | None) -> str | None:
    """Treat blank optional strings as omitted, matching the action spec."""
    if value is None or value == "":
        return None
    return value


def _normalize_optional_string_inputs(
    inputs: UpdatePullRequestInputs,
) -> UpdatePullRequestInputs:
    updates = {
        field: _blank_to_none(getattr(inputs, field))
        for field in OPTIONAL_STRING_FIELDS
        if getattr(inputs, field) == ""
    }
    if not updates:
        return inputs
    return inputs.model_copy(update=updates)


def _normalize_choice(
    value: str | None, allowed: Sequence[str], field_name: str
) -> Optional[str]:
    """Match a user-supplied value against the API's casing, or reject it."""
    normalized = _blank_to_none(value)
    if normalized is None:
        return None
    for candidate in allowed:
        if normalized.lower() == candidate.lower():
            return candidate
    raise InvalidActionParametersError(
        f"Invalid {field_name} '{normalized}'. Allowed values are: {', '.join(allowed)}"
    )


def _parse_policy_config_ids(value: str | None) -> list[int] | None:
    if value is None or value.strip() == "":
        return None
    policy_config_ids: list[int] = []
    for part in value.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        try:
            policy_config_ids.append(int(stripped))
        except ValueError as error:
            raise InvalidActionParametersError(
                "autoCompleteIgnoreConfigIds must be a comma-separated list of "
                f"integers, got invalid value '{stripped}'"
            ) from error
    if not policy_config_ids:
        return None
    return policy_config_ids


def _build_update_pull_request_body(
    inputs: UpdatePullRequestInputs,
    status: str | None,
    merge_strategy: str | None,
    last_merge_source_commit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if inputs.title is not None:
        body["title"] = inputs.title
    if inputs.description is not None:
        body["description"] = inputs.description
    if status is not None:
        body["status"] = status
    if inputs.targetBranch is not None:
        body["targetRefName"] = (
            inputs.targetBranch
            if inputs.targetBranch.startswith("refs/")
            else f"refs/heads/{inputs.targetBranch}"
        )
    if last_merge_source_commit:
        body["lastMergeSourceCommit"] = last_merge_source_commit
    if inputs.autoCompleteSetById is not None:
        body["autoCompleteSetBy"] = {"id": inputs.autoCompleteSetById}

    merge_options: dict[str, Any] = {}
    if inputs.disableRenames is not None:
        merge_options["disableRenames"] = inputs.disableRenames
    if inputs.conflictAuthorshipCommits is not None:
        merge_options["conflictAuthorshipCommits"] = inputs.conflictAuthorshipCommits
    if inputs.detectRenameFalsePositives is not None:
        merge_options["detectRenameFalsePositives"] = inputs.detectRenameFalsePositives
    if merge_options:
        body["mergeOptions"] = merge_options

    completion_options: dict[str, Any] = {}
    if merge_strategy is not None:
        completion_options["mergeStrategy"] = merge_strategy
    if inputs.deleteSourceBranch is not None:
        completion_options["deleteSourceBranch"] = inputs.deleteSourceBranch
    if inputs.mergeCommitMessage is not None:
        completion_options["mergeCommitMessage"] = inputs.mergeCommitMessage
    if inputs.bypassPolicy is not None:
        completion_options["bypassPolicy"] = inputs.bypassPolicy
    if inputs.bypassReason is not None:
        completion_options["bypassReason"] = inputs.bypassReason
    if inputs.transitionWorkItems is not None:
        completion_options["transitionWorkItems"] = inputs.transitionWorkItems
    policy_config_ids = _parse_policy_config_ids(inputs.autoCompleteIgnoreConfigIds)
    if policy_config_ids:
        completion_options["autoCompleteIgnoreConfigIds"] = policy_config_ids
    if completion_options:
        body["completionOptions"] = completion_options
    return body


def _has_update_fields(
    inputs: UpdatePullRequestInputs,
    status: str | None,
    merge_strategy: str | None,
) -> bool:
    return any(
        value is not None
        for value in (
            inputs.title,
            inputs.description,
            status,
            inputs.targetBranch,
            merge_strategy,
            inputs.deleteSourceBranch,
            inputs.mergeCommitMessage,
            inputs.bypassPolicy,
            inputs.bypassReason,
            inputs.transitionWorkItems,
            _parse_policy_config_ids(inputs.autoCompleteIgnoreConfigIds),
            inputs.disableRenames,
            inputs.conflictAuthorshipCommits,
            inputs.detectRenameFalsePositives,
            inputs.autoCompleteSetById,
        )
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
        try:
            inputs = _parse_update_pull_request_inputs(run.execution_properties)
        except ValueError as error:
            logger.warning(
                f"Invalid parameters for action run {run.id}",
                run_id=run.id,
                error=str(error),
            )
            raise InvalidActionParametersError(str(error)) from error

        inputs = _normalize_optional_string_inputs(inputs)

        if (
            inputs.description is not None
            and len(inputs.description) > MAX_DESCRIPTION_LENGTH
        ):
            logger.warning(
                f"Description exceeds the maximum length for action run {run.id}",
                run_id=run.id,
                description_length=len(inputs.description),
            )
            raise InvalidActionParametersError(
                f"description must be at most {MAX_DESCRIPTION_LENGTH} characters, "
                f"got {len(inputs.description)}"
            )

        status = _normalize_choice(inputs.status, VALID_STATUSES, "status")
        merge_strategy = _normalize_choice(
            inputs.mergeStrategy,
            VALID_MERGE_STRATEGIES,
            "mergeStrategy",
        )
        if not _has_update_fields(inputs, status, merge_strategy):
            logger.warning(
                f"No fields to update were provided for action run {run.id}",
                run_id=run.id,
                pull_request_id=inputs.pullRequestId,
            )
            raise InvalidActionParametersError(
                "At least one field to update is required: "
                f"{', '.join(UPDATE_FIELD_NAMES)}"
            )

        last_merge_source_commit: dict[str, Any] | None = None
        if status == COMPLETED_STATUS:
            last_merge_source_commit = await self._resolve_last_merge_source_commit(
                inputs.project,
                inputs.repositoryId,
                inputs.pullRequestId,
            )

        try:
            body = _build_update_pull_request_body(
                inputs,
                status,
                merge_strategy,
                last_merge_source_commit,
            )
        except InvalidActionParametersError:
            raise

        await ocean.port_client.post_run_log(
            run,
            f"Updating pull request {inputs.pullRequestId} in repository "
            f"'{inputs.repositoryId}'",
        )

        try:
            pull_request = await self.client.update_pull_request(
                inputs.project,
                inputs.repositoryId,
                inputs.pullRequestId,
                body,
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Azure DevOps rejected the update of pull request "
                f"{inputs.pullRequestId} for action run {run.id}: "
                f"HTTP {e.response.status_code}",
                run_id=run.id,
                project_id=inputs.project,
                repository_id=inputs.repositoryId,
                pull_request_id=inputs.pullRequestId,
                status_code=e.response.status_code,
            )
            raise UpdatePullRequestError.from_response(
                e.response,
                f"Error updating pull request {inputs.pullRequestId} in repository "
                f"'{inputs.repositoryId}'",
            )

        if not pull_request or "pullRequestId" not in pull_request:
            logger.error(
                f"Azure DevOps returned an unexpected response while updating pull "
                f"request {inputs.pullRequestId} for action run {run.id}",
                run_id=run.id,
                pull_request_id=inputs.pullRequestId,
            )
            raise UpdatePullRequestError(
                f"Azure DevOps returned an unexpected response while updating pull "
                f"request {inputs.pullRequestId}"
            )

        updated_status = pull_request.get("status", "unknown")
        link = pull_request.get("_links", {}).get("web", {}).get("href", "")
        logger.info(
            f"Pull request {inputs.pullRequestId} updated for action run {run.id}",
            run_id=run.id,
            pull_request_id=inputs.pullRequestId,
            status=updated_status,
            link=link,
        )
        message = (
            f"Pull request {inputs.pullRequestId} updated, its status is now "
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
        repository_id = properties.get("repositoryId")
        pull_request_id = properties.get("pullRequestId")
        if not (project and repository_id and pull_request_id):
            return None
        return f"{project}/{repository_id}/{pull_request_id}"

    async def _resolve_last_merge_source_commit(
        self,
        project: str,
        repository_id: str,
        pull_request_id: str,
    ) -> dict[str, Any]:
        """Fetch the source commit that completing the pull request must merge.

        Azure DevOps requires it so the merge runs against the source version
        the caller last saw, and rejects the completion otherwise.
        """
        pull_request = await self.client.get_repository_pull_request(
            project,
            repository_id,
            pull_request_id,
        )
        if not pull_request:
            raise InvalidActionParametersError(
                f"Pull request {pull_request_id} was not found"
            )
        last_merge_source_commit = pull_request.get("lastMergeSourceCommit")
        if not isinstance(
            last_merge_source_commit, dict
        ) or not last_merge_source_commit.get("commitId"):
            raise UpdatePullRequestError(
                f"Pull request {pull_request_id} cannot be completed: Azure DevOps has "
                "not published a merge commit for its source branch yet"
            )
        return last_merge_source_commit
