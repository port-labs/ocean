import httpx
from loguru import logger
from pydantic import model_validator

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import EditIssueError

class EditIssueInputs(AbstractGithubActionInput):
    org: str
    repo: str
    issueNumber: int
    title: str | None = None
    body: str | None = None
    labels: list[str] | None = None
    assignees: list[str] | None = None
    milestone: int | None = None

    @model_validator(mode="after")
    def check_at_least_one_update_field(self) -> "EditIssueInputs":
        if not any([
            self.title is not None,
            self.body is not None,
            self.labels is not None,
            self.assignees is not None,
            self.milestone is not None,
        ]):
            raise ValueError(
                "At least one field to update is required (title, body, labels, assignees, or milestone)"
            )
        return self


class EditIssueExecutor(AbstractGithubExecutor):
    ACTION_NAME = "edit_issue"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = EditIssueInputs.from_execution_properties(
            run.execution_properties
        )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Editing issue #{inputs.issueNumber} in {inputs.org}/{inputs.repo}",
            status_label="Editing issue",
            should_raise=False,
        )

        patch_body: dict[str, str | int | list[str] | None] = {}
        if inputs.title is not None:
            patch_body["title"] = inputs.title
        if inputs.body is not None:
            patch_body["body"] = inputs.body
        if inputs.labels is not None:
            patch_body["labels"] = inputs.labels
        if inputs.assignees is not None:
            patch_body["assignees"] = inputs.assignees
        if inputs.milestone is not None:
            patch_body["milestone"] = inputs.milestone

        try:
            issue = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/issues/{inputs.issueNumber}",
                method="PATCH",
                json_data=patch_body,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise EditIssueError.from_response(
                e.response,
                f"Could not edit issue #{inputs.issueNumber} in {inputs.org}/{inputs.repo}",
            )

        issue_number = issue.get("number")
        if issue_number is None:
            raise EditIssueError(
                "Failed to edit issue: GitHub returned an empty or incomplete response"
            )

        message = f"Issue #{issue_number} updated: {issue['html_url']}"
        logger.info(
            f"Edited issue #{issue_number} in {inputs.org}/{inputs.repo}",
            issue_number=issue_number,
            html_url=issue["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue updated",
        )
