from typing import Any, Literal

import httpx
from loguru import logger
from pydantic.v1 import BaseModel, ValidationError, root_validator, validator
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from gitlab.actions.abstract_gitlab_executor import AbstractGitlabExecutor
from gitlab.helpers.exceptions import (
    GitlabUpdateMergeRequestError,
    MissingExecutionPropertyError,
)

VALID_STATE_EVENTS = ("close", "reopen")


def _parse_user_ids(value: Any, field_name: str) -> list[int] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(
            f"{field_name} must be an array of user IDs, got {type(value).__name__}"
        )

    ids: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            if isinstance(item, str) and item.strip().lstrip("-").isdigit():
                ids.append(int(item))
                continue
            raise ValueError(
                f"{field_name} must contain integer user IDs, got {item!r}"
            )
        ids.append(item)
    return ids


class UpdateMergeRequestInput(BaseModel):
    id: str
    mergeRequestIid: str
    title: str | None = None
    description: str | None = None
    stateEvent: Literal["close", "reopen"] | None = None
    targetBranch: str | None = None
    assigneeIds: list[int] | None = None
    reviewerIds: list[int] | None = None

    class Config:
        extra = "ignore"

    @validator("id", "mergeRequestIid", pre=True, always=True)
    def require_non_empty_str(cls, value: Any, field: Any) -> str:
        if value is None or (isinstance(value, str) and not str(value).strip()):
            raise ValueError(f"{field.name} is required")
        return str(value)

    @validator("title", "description", "stateEvent", "targetBranch", pre=True)
    def empty_optional_str_as_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @validator("stateEvent", pre=True)
    def validate_state_event(cls, value: Any) -> Any:
        if value is None:
            return None
        if value not in VALID_STATE_EVENTS:
            raise ValueError(
                f"stateEvent must be one of {sorted(VALID_STATE_EVENTS)}, got {value!r}"
            )
        return value

    @validator("assigneeIds", "reviewerIds", pre=True)
    def validate_user_ids(cls, value: Any, field: Any) -> list[int] | None:
        return _parse_user_ids(value, field.name)

    @root_validator(skip_on_failure=True)
    def require_at_least_one_update(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not any(
            values.get(name) is not None
            for name in (
                "title",
                "description",
                "stateEvent",
                "targetBranch",
                "assigneeIds",
                "reviewerIds",
            )
        ):
            raise ValueError(
                "At least one of title, description, stateEvent, targetBranch, "
                "assigneeIds, or reviewerIds is required"
            )
        return values

    @classmethod
    def from_execution_properties(
        cls, execution_properties: dict[str, Any]
    ) -> "UpdateMergeRequestInput":
        try:
            return cls.parse_obj(execution_properties)
        except ValidationError as error:
            raise MissingExecutionPropertyError(str(error)) from error

    def to_gitlab_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.title is not None:
            payload["title"] = self.title
        if self.description is not None:
            payload["description"] = self.description
        if self.stateEvent is not None:
            payload["state_event"] = self.stateEvent
        if self.targetBranch is not None:
            payload["target_branch"] = self.targetBranch
        if self.assigneeIds is not None:
            payload["assignee_ids"] = self.assigneeIds
        if self.reviewerIds is not None:
            payload["reviewer_ids"] = self.reviewerIds
        return payload


class UpdateMergeRequestExecutor(AbstractGitlabExecutor):
    ACTION_NAME = "update_merge_request"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        project_id = run.execution_properties.get("id")
        merge_request_iid = run.execution_properties.get("mergeRequestIid")
        if not project_id or not merge_request_iid:
            return None
        return f"{project_id}/{merge_request_iid}"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = UpdateMergeRequestInput.from_execution_properties(
            run.execution_properties
        )
        payload = inputs.to_gitlab_payload()

        await ocean.port_client.post_run_log(
            run,
            f"Updating merge request !{inputs.mergeRequestIid} in project {inputs.id}",
            should_raise=False,
        )

        try:
            merge_request = await self.client.update_merge_request(
                inputs.id, inputs.mergeRequestIid, payload
            )
        except httpx.HTTPStatusError as e:
            raise GitlabUpdateMergeRequestError.from_response(
                e.response,
                f"Could not update merge request !{inputs.mergeRequestIid} "
                f"in project '{inputs.id}'",
            )

        if not merge_request or not all(k in merge_request for k in ("iid", "web_url")):
            raise GitlabUpdateMergeRequestError(
                "Failed to update merge request: GitLab returned an empty or incomplete response"
            )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Updated merge request: {merge_request['web_url']}",
        )
        logger.info(
            f"Updated merge request !{merge_request['iid']} in project {inputs.id}",
            project=inputs.id,
            merge_request_iid=merge_request["iid"],
            web_url=merge_request["web_url"],
        )
