from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from pydantic.v1 import BaseModel, ValidationError, validator

from gitlab.actions.abstract_gitlab_executor import AbstractGitlabExecutor
from gitlab.helpers.exceptions import (
    GitlabCreateMergeRequestCommentError,
    MissingExecutionPropertyError,
)

CREATING_COMMENT_STATUS_LABEL = "Creating comment"
COMMENT_CREATED_STATUS_LABEL = "Comment created"


class CreateMergeRequestCommentInput(BaseModel):
    project: str
    mergeRequestIid: int
    body: str

    class Config:
        extra = "ignore"

    @validator("project", "body", pre=True, always=True)
    def require_non_empty_str(cls, value: Any, field: Any) -> str:
        if value is None or (isinstance(value, str) and not str(value).strip()):
            raise ValueError(f"{field.name} is required")
        return str(value)

    @validator("mergeRequestIid", pre=True)
    def require_merge_request_iid(cls, value: Any) -> int:
        if value is None or (isinstance(value, str) and not str(value).strip()):
            raise ValueError("mergeRequestIid is required")
        try:
            return int(str(value).strip())
        except ValueError as error:
            raise ValueError(
                "mergeRequestIid must be a valid merge request IID"
            ) from error

    @classmethod
    def from_execution_properties(
        cls, execution_properties: dict[str, Any]
    ) -> "CreateMergeRequestCommentInput":
        try:
            return cls.parse_obj(execution_properties)
        except ValidationError as error:
            raise MissingExecutionPropertyError(
                cls._validation_error_message(error)
            ) from error

    @staticmethod
    def _validation_error_message(error: ValidationError) -> str:
        first_error = error.errors()[0]
        field_name = first_error["loc"][0]
        if first_error["type"] == "value_error.missing":
            return f"{field_name} is required"
        return str(first_error["msg"])


class CreateMergeRequestCommentExecutor(AbstractGitlabExecutor):
    ACTION_NAME = "create_merge_request_comment"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateMergeRequestCommentInput.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Creating comment on merge request !{inputs.mergeRequestIid} in {inputs.project}",
            status_label=CREATING_COMMENT_STATUS_LABEL,
            should_raise=False,
        )

        try:
            note = await self.client.create_merge_request_note(
                inputs.project, inputs.mergeRequestIid, inputs.body
            )
        except httpx.HTTPStatusError as error:
            raise GitlabCreateMergeRequestCommentError.from_response(
                error.response,
                f"Could not create comment on merge request !{inputs.mergeRequestIid} "
                f"in project '{inputs.project}'",
            )

        note_id = note.get("id") if note else None
        if note_id is None:
            raise GitlabCreateMergeRequestCommentError(
                "Failed to create merge request comment: GitLab returned an empty or "
                "incomplete response"
            )

        message = f"Created merge request comment (note ID {note_id})"
        await ocean.port_client.post_run_log(
            run,
            message,
            should_raise=False,
        )
        logger.info(
            "Created merge request comment",
            note_id=note_id,
            merge_request_iid=inputs.mergeRequestIid,
            project=inputs.project,
        )

        if isinstance(run, WorkflowNodeRun):
            run.output = {
                "noteId": str(note_id),
                "mergeRequestIid": str(inputs.mergeRequestIid),
            }

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label=COMMENT_CREATED_STATUS_LABEL,
        )
