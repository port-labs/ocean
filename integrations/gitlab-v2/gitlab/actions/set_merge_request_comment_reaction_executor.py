from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from pydantic.v1 import BaseModel, ValidationError, validator

from gitlab.actions.abstract_gitlab_executor import AbstractGitlabExecutor
from gitlab.helpers.exceptions import (
    GitlabSetMergeRequestCommentReactionError,
    MissingExecutionPropertyError,
)

ADDING_REACTION_STATUS_LABEL = "Adding reaction"
REMOVING_REACTION_STATUS_LABEL = "Removing reaction"
REACTION_UPDATED_STATUS_LABEL = "Reaction updated"


class SetMergeRequestCommentReactionInput(BaseModel):
    project: str
    mergeRequestIid: int
    noteId: int
    name: str
    removeReaction: bool = False

    class Config:
        extra = "ignore"

    @validator("project", "name", pre=True, always=True)
    def require_non_empty_str(cls, value: Any, field: Any) -> str:
        if value is None or (isinstance(value, str) and not str(value).strip()):
            raise ValueError(f"{field.name} is required")
        return str(value).strip()

    @validator("mergeRequestIid", "noteId", pre=True)
    def require_int_id(cls, value: Any, field: Any) -> int:
        if value is None or (isinstance(value, str) and not str(value).strip()):
            raise ValueError(f"{field.name} is required")
        try:
            return int(str(value).strip())
        except ValueError as error:
            raise ValueError(f"{field.name} must be a valid ID") from error

    @validator("removeReaction", pre=True)
    def require_bool(cls, value: Any) -> bool:
        if not isinstance(value, bool):
            raise ValueError("removeReaction must be a boolean")
        return value

    @classmethod
    def from_execution_properties(
        cls, execution_properties: dict[str, Any]
    ) -> "SetMergeRequestCommentReactionInput":
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


class SetMergeRequestCommentReactionExecutor(AbstractGitlabExecutor):
    ACTION_NAME = "set_merge_request_comment_reaction"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        inputs = SetMergeRequestCommentReactionInput.from_execution_properties(
            run.execution_properties
        )

        if inputs.removeReaction:
            message = await self._remove_reaction(run, inputs)
            award_id = None
        else:
            message, award_id = await self._add_reaction(run, inputs)

        await self._report_success(run, inputs, message, award_id)

    async def _add_reaction(
        self, run: IntegrationRun, inputs: SetMergeRequestCommentReactionInput
    ) -> tuple[str, str]:
        await ocean.port_client.post_run_log(
            run,
            f"Adding reaction '{inputs.name}' to note {inputs.noteId} on merge request "
            f"!{inputs.mergeRequestIid} in {inputs.project}",
            status_label=ADDING_REACTION_STATUS_LABEL,
            should_raise=False,
        )
        try:
            award = await self.client.award_merge_request_note_emoji(
                inputs.project, inputs.mergeRequestIid, inputs.noteId, inputs.name
            )
        except httpx.HTTPStatusError as error:
            raise GitlabSetMergeRequestCommentReactionError.from_response(
                error.response,
                f"Could not add reaction '{inputs.name}' to note {inputs.noteId} on merge "
                f"request !{inputs.mergeRequestIid} in project '{inputs.project}'",
            )

        award_id = award.get("id") if award else None
        if award_id is None:
            raise GitlabSetMergeRequestCommentReactionError(
                "Failed to set merge request comment reaction: GitLab returned an empty or "
                "incomplete response"
            )
        message = (
            f"Added reaction '{inputs.name}' to merge request comment (note ID "
            f"{inputs.noteId}, award ID {award_id})"
        )
        return message, str(award_id)

    async def _remove_reaction(
        self, run: IntegrationRun, inputs: SetMergeRequestCommentReactionInput
    ) -> str:
        await ocean.port_client.post_run_log(
            run,
            f"Removing reaction '{inputs.name}' from note {inputs.noteId} on merge request "
            f"!{inputs.mergeRequestIid} in {inputs.project}",
            status_label=REMOVING_REACTION_STATUS_LABEL,
            should_raise=False,
        )
        try:
            award_id = await self._find_award_id(inputs)
            await self.client.revoke_merge_request_note_award_emoji(
                inputs.project, inputs.mergeRequestIid, inputs.noteId, award_id
            )
        except httpx.HTTPStatusError as error:
            raise GitlabSetMergeRequestCommentReactionError.from_response(
                error.response,
                f"Could not remove reaction '{inputs.name}' from note {inputs.noteId} on "
                f"merge request !{inputs.mergeRequestIid} in project '{inputs.project}'",
            )
        return (
            f"Removed reaction '{inputs.name}' from merge request comment (note ID "
            f"{inputs.noteId})"
        )

    async def _find_award_id(self, inputs: SetMergeRequestCommentReactionInput) -> int:
        # GitLab revokes a reaction by award ID, but the action receives the emoji
        # name, so we look up the award whose name matches to get its ID.
        awards = await self.client.list_merge_request_note_award_emojis(
            inputs.project, inputs.mergeRequestIid, inputs.noteId
        )
        normalized = inputs.name.lower()
        for award in awards:
            if award.name.lower() == normalized:
                return award.id
        raise GitlabSetMergeRequestCommentReactionError(
            f"No reaction '{inputs.name}' found on note {inputs.noteId} to remove"
        )

    async def _report_success(
        self,
        run: IntegrationRun,
        inputs: SetMergeRequestCommentReactionInput,
        message: str,
        award_id: str | None,
    ) -> None:
        logger.info(
            "Updated merge request comment reaction",
            project=inputs.project,
            merge_request_iid=inputs.mergeRequestIid,
            note_id=inputs.noteId,
            name=inputs.name,
            removed=inputs.removeReaction,
        )

        if isinstance(run, WorkflowNodeRun):
            run.output = {
                "noteId": str(inputs.noteId),
                "mergeRequestIid": str(inputs.mergeRequestIid),
                "name": inputs.name,
                "removed": inputs.removeReaction,
            }
            if award_id is not None:
                run.output["awardId"] = award_id

        await ocean.port_client.post_run_log(run, message, should_raise=False)
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label=REACTION_UPDATED_STATUS_LABEL,
        )
