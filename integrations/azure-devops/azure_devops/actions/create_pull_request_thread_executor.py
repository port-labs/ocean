from typing import Any, Optional, Sequence

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from azure_devops.actions.abstract_ado_executor import AbstractAzureDevopsExecutor
from azure_devops.actions.exceptions import (
    CreatePullRequestThreadError,
    InvalidActionParametersError,
)

# The API also defines "unknown", which is the absence of a status rather than
# something a user would open a thread with.
VALID_THREAD_STATUSES = (
    "active",
    "fixed",
    "wontFix",
    "closed",
    "byDesign",
    "pending",
)
# A thread opened through an action is a regular user comment; the remaining
# CommentType values ("codeChange", "system") are set by Azure DevOps itself.
COMMENT_TYPE_TEXT = "text"
# The first comment of a thread has no parent.
ROOT_PARENT_COMMENT_ID = 0
# Azure DevOps counts a CommentPosition's line from 1 and its character offset
# from 0. The action takes a line rather than a character range, so both ends of
# the span sit at the first character, which anchors the thread to the line.
FIRST_LINE = 1
LINE_START_OFFSET = 1

OPTIONAL_STRING_FIELDS = (
    "status",
    "filePath",
    "line",
)


class CreatePullRequestThreadInputs(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    project: str = Field(min_length=1)
    repositoryId: str = Field(min_length=1)
    pullRequestId: str = Field(min_length=1)
    content: str = Field(min_length=1)
    status: str | None = None
    filePath: str | None = None
    line: str | None = None


def _parse_create_pull_request_thread_inputs(
    execution_properties: dict[str, Any],
) -> CreatePullRequestThreadInputs:
    try:
        return CreatePullRequestThreadInputs.model_validate(execution_properties)
    except ValidationError as error:
        messages = [
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
            for err in error.errors()
        ]
        raise ValueError("; ".join(messages)) from error


def _blank_to_none(value: str | None) -> str | None:
    """Treat blank optional strings as omitted, matching the action spec."""
    if value is None or value == "":
        return None
    return value


def _normalize_optional_string_inputs(
    inputs: CreatePullRequestThreadInputs,
) -> CreatePullRequestThreadInputs:
    updates = {
        field: _blank_to_none(getattr(inputs, field))
        for field in OPTIONAL_STRING_FIELDS
    }
    if all(
        getattr(inputs, field) == updates[field] for field in OPTIONAL_STRING_FIELDS
    ):
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


def _parse_line(value: str | None) -> int | None:
    normalized = _blank_to_none(value)
    if normalized is None:
        return None
    try:
        line = int(normalized.strip())
    except ValueError as error:
        raise InvalidActionParametersError(
            f"line must be an integer, got invalid value '{normalized}'"
        ) from error
    if line < FIRST_LINE:
        raise InvalidActionParametersError(
            f"line must be {FIRST_LINE} or greater, got {line}"
        )
    return line


def _build_create_pull_request_thread_body(
    inputs: CreatePullRequestThreadInputs,
    status: str | None,
    line: int | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "comments": [
            {
                "parentCommentId": ROOT_PARENT_COMMENT_ID,
                "content": inputs.content,
                "commentType": COMMENT_TYPE_TEXT,
            }
        ]
    }
    if status is not None:
        body["status"] = status

    file_path = _blank_to_none(inputs.filePath)
    if file_path is not None:
        thread_context: dict[str, Any] = {"filePath": file_path}
        if line is not None:
            # Span the whole line: Azure DevOps needs both ends of the span, and
            # the action takes a line rather than a character range.
            thread_context["rightFileStart"] = {
                "line": line,
                "offset": LINE_START_OFFSET,
            }
            thread_context["rightFileEnd"] = {
                "line": line,
                "offset": LINE_START_OFFSET,
            }
        body["threadContext"] = thread_context
    return body


class CreatePullRequestThreadExecutor(AbstractAzureDevopsExecutor):
    """Executor for creating a comment thread on an Azure DevOps pull request.

    Azure DevOps' Create Pull Request Thread API creates the thread and returns
    it in the same call, so the run is completed here rather than waiting for a
    service hook.

    No partition key is set: each run adds a new thread instead of mutating a
    shared one, so concurrent runs on the same pull request cannot conflict.
    """

    ACTION_NAME = "create_pull_request_thread"

    async def execute(self, run: IntegrationRun) -> None:
        logger.info(
            f"Creating pull request comment thread for action run {run.id}",
            run_id=run.id,
        )
        try:
            inputs = _parse_create_pull_request_thread_inputs(run.execution_properties)
        except ValueError as error:
            logger.warning(
                f"Invalid parameters for action run {run.id}",
                run_id=run.id,
                error=str(error),
            )
            raise InvalidActionParametersError(str(error)) from error

        inputs = _normalize_optional_string_inputs(inputs)

        status = _normalize_choice(inputs.status, VALID_THREAD_STATUSES, "status")
        line = _parse_line(inputs.line)
        if line is not None and _blank_to_none(inputs.filePath) is None:
            logger.warning(
                f"line was provided without filePath for action run {run.id}",
                run_id=run.id,
                pull_request_id=inputs.pullRequestId,
            )
            raise InvalidActionParametersError(
                "line requires filePath: a line number only anchors a thread when "
                "the file it belongs to is also provided"
            )

        body = _build_create_pull_request_thread_body(inputs, status, line)

        await ocean.port_client.post_run_log(
            run,
            f"Creating a comment thread on pull request {inputs.pullRequestId} in "
            f"repository '{inputs.repositoryId}'",
        )

        try:
            thread = await self.client.create_pull_request_thread(
                inputs.project,
                inputs.repositoryId,
                inputs.pullRequestId,
                body,
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Azure DevOps rejected the comment thread on pull request "
                f"{inputs.pullRequestId} for action run {run.id}: "
                f"HTTP {e.response.status_code}",
                run_id=run.id,
                project_id=inputs.project,
                repository_id=inputs.repositoryId,
                pull_request_id=inputs.pullRequestId,
                status_code=e.response.status_code,
            )
            raise CreatePullRequestThreadError.from_response(
                e.response,
                f"Error creating a comment thread on pull request "
                f"{inputs.pullRequestId} in repository '{inputs.repositoryId}'",
            )

        if not thread or "id" not in thread:
            logger.error(
                f"Azure DevOps returned an unexpected response while creating a "
                f"comment thread on pull request {inputs.pullRequestId} for action "
                f"run {run.id}",
                run_id=run.id,
                pull_request_id=inputs.pullRequestId,
            )
            raise CreatePullRequestThreadError(
                f"Azure DevOps returned an unexpected response while creating a "
                f"comment thread on pull request {inputs.pullRequestId}"
            )

        thread_id = thread["id"]
        thread_status = thread.get("status", "unknown")
        logger.info(
            f"Comment thread {thread_id} created on pull request "
            f"{inputs.pullRequestId} for action run {run.id}",
            run_id=run.id,
            pull_request_id=inputs.pullRequestId,
            thread_id=thread_id,
            status=thread_status,
        )
        message = (
            f"Comment thread {thread_id} created on pull request "
            f"{inputs.pullRequestId} with status '{thread_status}'"
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Created",
        )
