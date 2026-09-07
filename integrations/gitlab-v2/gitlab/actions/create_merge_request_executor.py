import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from gitlab.actions.abstract_gitlab_executor import AbstractGitlabExecutor
from gitlab.helpers.exceptions import (
    GitlabCreateMergeRequestError,
    MissingExecutionPropertyError,
)


class CreateMergeRequestExecutor(AbstractGitlabExecutor):
    ACTION_NAME = "create_merge_request"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        project = run.execution_properties.get("project")
        source_branch = run.execution_properties.get("sourceBranch")
        target_branch = run.execution_properties.get("targetBranch")
        title = run.execution_properties.get("title")

        if not project:
            raise MissingExecutionPropertyError("project is required")
        if not source_branch:
            raise MissingExecutionPropertyError("sourceBranch is required")
        if not target_branch:
            raise MissingExecutionPropertyError("targetBranch is required")
        if not title:
            raise MissingExecutionPropertyError("title is required")

        await ocean.port_client.post_run_log(
            run,
            f"Creating merge request in {project}: {source_branch} -> {target_branch}",
            should_raise=False,
        )

        try:
            merge_request = await self.client.create_merge_request(
                project, source_branch, target_branch, title
            )
        except httpx.HTTPStatusError as e:
            raise GitlabCreateMergeRequestError.from_response(
                e.response,
                f"Could not create merge request in project '{project}'",
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
            f"Merge request {merge_request['id']} created in project {project}",
            merge_request_id=merge_request["id"],
            project=project,
            source_branch=source_branch,
            target_branch=target_branch,
        )
