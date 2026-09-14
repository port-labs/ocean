import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from gitlab.actions.abstract_gitlab_executor import AbstractGitlabExecutor
from gitlab.helpers.exceptions import (
    GitlabCreateMergeRequestCommentError,
    MissingExecutionPropertyError,
)

CREATING_COMMENT_STATUS_LABEL = "Creating comment"
COMMENT_CREATED_STATUS_LABEL = "Comment created"


class CreateMergeRequestCommentExecutor(AbstractGitlabExecutor):
    ACTION_NAME = "create_merge_request_comment"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        project = run.execution_properties.get("project")
        merge_request_iid_raw = run.execution_properties.get("mergeRequestIid")
        body = run.execution_properties.get("body")

        if not project:
            raise MissingExecutionPropertyError("project is required")
        if merge_request_iid_raw is None or str(merge_request_iid_raw).strip() == "":
            raise MissingExecutionPropertyError("mergeRequestIid is required")
        if not body:
            raise MissingExecutionPropertyError("body is required")

        try:
            merge_request_iid = int(str(merge_request_iid_raw).strip())
        except ValueError as error:
            raise MissingExecutionPropertyError(
                "mergeRequestIid must be a valid merge request IID"
            ) from error

        await ocean.port_client.post_run_log(
            run,
            f"Creating comment on merge request !{merge_request_iid} in {project}",
            status_label=CREATING_COMMENT_STATUS_LABEL,
            should_raise=False,
        )

        try:
            note = await self.client.create_merge_request_note(
                project, merge_request_iid, str(body)
            )
        except httpx.HTTPStatusError as error:
            raise GitlabCreateMergeRequestCommentError.from_response(
                error.response,
                f"Could not create comment on merge request !{merge_request_iid} "
                f"in project '{project}'",
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
            merge_request_iid=merge_request_iid,
            project=project,
        )

        if isinstance(run, WorkflowNodeRun):
            run.output = {
                "noteId": str(note_id),
                "mergeRequestIid": str(merge_request_iid),
            }

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label=COMMENT_CREATED_STATUS_LABEL,
        )
