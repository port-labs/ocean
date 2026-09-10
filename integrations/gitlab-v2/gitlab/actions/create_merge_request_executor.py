from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic.v1 import BaseModel, ValidationError, validator

from gitlab.actions.abstract_gitlab_executor import AbstractGitlabExecutor
from gitlab.helpers.exceptions import (
    GitlabCreateMergeRequestError,
    MissingExecutionPropertyError,
)


class CreateMergeRequestInput(BaseModel):
    project: str
    sourceBranch: str
    targetBranch: str
    title: str

    class Config:
        extra = "ignore"

    @validator(
        "project", "sourceBranch", "targetBranch", "title", pre=True, always=True
    )
    def require_non_empty_str(cls, value: Any, field: Any) -> str:
        if value is None or (isinstance(value, str) and not str(value).strip()):
            raise ValueError(f"{field.name} is required")
        return str(value)

    @classmethod
    def from_execution_properties(
        cls, execution_properties: dict[str, Any]
    ) -> "CreateMergeRequestInput":
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


class CreateMergeRequestExecutor(AbstractGitlabExecutor):
    ACTION_NAME = "create_merge_request"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateMergeRequestInput.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Creating merge request in {inputs.project}: "
            f"{inputs.sourceBranch} -> {inputs.targetBranch}",
            should_raise=False,
        )

        try:
            merge_request = await self.client.create_merge_request(
                inputs.project,
                inputs.sourceBranch,
                inputs.targetBranch,
                inputs.title,
            )
        except httpx.HTTPStatusError as e:
            raise GitlabCreateMergeRequestError.from_response(
                e.response,
                f"Could not create merge request in project '{inputs.project}'",
            )

        if not merge_request or not all(k in merge_request for k in ("id", "web_url")):
            raise GitlabCreateMergeRequestError(
                "Failed to create merge request: GitLab returned an empty or incomplete response"
            )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Merge request created: {merge_request['web_url']}",
        )
        await ocean.port_client.post_run_log(
            run,
            f"Merge request created: {merge_request['web_url']}",
            should_raise=False,
        )
        logger.info(
            f"Merge request {merge_request['id']} created in project {inputs.project}",
            merge_request_id=merge_request["id"],
            project=inputs.project,
            source_branch=inputs.sourceBranch,
            target_branch=inputs.targetBranch,
        )
