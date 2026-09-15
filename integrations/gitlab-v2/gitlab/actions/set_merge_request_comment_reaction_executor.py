import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from gitlab.actions.abstract_gitlab_executor import AbstractGitlabExecutor
from gitlab.helpers.exceptions import (
    GitlabSetMergeRequestCommentReactionError,
    MissingExecutionPropertyError,
)

ADDING_REACTION_STATUS_LABEL = "Adding reaction"
REMOVING_REACTION_STATUS_LABEL = "Removing reaction"
REACTION_UPDATED_STATUS_LABEL = "Reaction updated"


class SetMergeRequestCommentReactionExecutor(AbstractGitlabExecutor):
    ACTION_NAME = "set_merge_request_comment_reaction"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        project = run.execution_properties.get("project")
        merge_request_iid_raw = run.execution_properties.get("mergeRequestIid")
        note_id_raw = run.execution_properties.get("noteId")
        name = run.execution_properties.get("name")
        remove_reaction = run.execution_properties.get("removeReaction", False)

        if not project:
            raise MissingExecutionPropertyError("project is required")
        if merge_request_iid_raw is None or str(merge_request_iid_raw).strip() == "":
            raise MissingExecutionPropertyError("mergeRequestIid is required")
        if note_id_raw is None or str(note_id_raw).strip() == "":
            raise MissingExecutionPropertyError("noteId is required")
        if not name or not str(name).strip():
            raise MissingExecutionPropertyError("name is required")
        if not isinstance(remove_reaction, bool):
            raise MissingExecutionPropertyError("removeReaction must be a boolean")

        try:
            merge_request_iid = int(str(merge_request_iid_raw).strip())
        except ValueError as error:
            raise MissingExecutionPropertyError(
                "mergeRequestIid must be a valid merge request IID"
            ) from error

        try:
            note_id = int(str(note_id_raw).strip())
        except ValueError as error:
            raise MissingExecutionPropertyError(
                "noteId must be a valid merge request note ID"
            ) from error

        emoji_name = str(name).strip()

        if remove_reaction:
            await ocean.port_client.post_run_log(
                run,
                f"Removing reaction '{emoji_name}' from note {note_id} on merge request "
                f"!{merge_request_iid} in {project}",
                status_label=REMOVING_REACTION_STATUS_LABEL,
                should_raise=False,
            )
            try:
                award_id = await self._find_award_id(
                    project, merge_request_iid, note_id, emoji_name
                )
                await self.client.revoke_merge_request_note_award_emoji(
                    project, merge_request_iid, note_id, award_id
                )
            except httpx.HTTPStatusError as error:
                raise GitlabSetMergeRequestCommentReactionError.from_response(
                    error.response,
                    f"Could not remove reaction '{emoji_name}' from note {note_id} on merge "
                    f"request !{merge_request_iid} in project '{project}'",
                )
            message = f"Removed reaction '{emoji_name}' from merge request comment (note ID {note_id})"
            output_award_id: str | None = None
        else:
            await ocean.port_client.post_run_log(
                run,
                f"Adding reaction '{emoji_name}' to note {note_id} on merge request "
                f"!{merge_request_iid} in {project}",
                status_label=ADDING_REACTION_STATUS_LABEL,
                should_raise=False,
            )
            try:
                award = await self.client.award_merge_request_note_emoji(
                    project, merge_request_iid, note_id, emoji_name
                )
            except httpx.HTTPStatusError as error:
                raise GitlabSetMergeRequestCommentReactionError.from_response(
                    error.response,
                    f"Could not add reaction '{emoji_name}' to note {note_id} on merge request "
                    f"!{merge_request_iid} in project '{project}'",
                )

            award_id_raw = award.get("id") if award else None
            if award_id_raw is None:
                raise GitlabSetMergeRequestCommentReactionError(
                    "Failed to set merge request comment reaction: GitLab returned an empty or "
                    "incomplete response"
                )
            message = (
                f"Added reaction '{emoji_name}' to merge request comment (note ID {note_id}, "
                f"award ID {award_id_raw})"
            )
            output_award_id = str(award_id_raw)

        logger.info(
            "Updated merge request comment reaction",
            project=project,
            merge_request_iid=merge_request_iid,
            note_id=note_id,
            name=emoji_name,
            removed=remove_reaction,
        )

        if isinstance(run, WorkflowNodeRun):
            run.output = {
                "noteId": str(note_id),
                "mergeRequestIid": str(merge_request_iid),
                "name": emoji_name,
                "removed": remove_reaction,
            }
            if output_award_id is not None:
                run.output["awardId"] = output_award_id

        await ocean.port_client.post_run_log(run, message, should_raise=False)
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label=REACTION_UPDATED_STATUS_LABEL,
        )

    async def _find_award_id(
        self,
        project: str,
        merge_request_iid: int,
        note_id: int,
        emoji_name: str,
    ) -> int:
        awards = await self.client.list_merge_request_note_award_emojis(
            project, merge_request_iid, note_id
        )
        normalized = emoji_name.lower()
        for award in awards:
            award_name = award.get("name")
            if isinstance(award_name, str) and award_name.lower() == normalized:
                award_id = award.get("id")
                if award_id is not None:
                    return int(award_id)
        raise GitlabSetMergeRequestCommentReactionError(
            f"No reaction '{emoji_name}' found on note {note_id} to remove"
        )
