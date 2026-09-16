from typing import Any

import httpx
from loguru import logger
from pydantic import Field

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import CreateIssueError


class CreateIssueInputs(AbstractGithubActionInput):
    org: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str | None = None
    labels: list[str] | None = None
    assignees: list[str] | None = None
    milestone: int | None = None

    def to_api_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": self.title}
        if self.body is not None:
            payload["body"] = self.body
        if self.labels is not None:
            payload["labels"] = self.labels
        if self.assignees is not None:
            payload["assignees"] = self.assignees
        if self.milestone is not None:
            payload["milestone"] = self.milestone
        return payload


class CreateIssueExecutor(AbstractGithubExecutor):
    ACTION_NAME = "create_issue"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateIssueInputs.from_execution_properties(run.execution_properties)

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Creating issue '{inputs.title}' in {inputs.org}/{inputs.repo}",
            status_label="Creating issue",
            should_raise=False,
        )

        try:
            issue = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/issues",
                method="POST",
                json_data=inputs.to_api_payload(),
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise CreateIssueError.from_response(
                e.response, f"Could not create issue in {inputs.org}/{inputs.repo}"
            )

        issue_number = issue.get("number")
        if issue_number is None:
            raise CreateIssueError(
                "Failed to create issue: GitHub returned an empty or incomplete response"
            )

        message = f"Issue #{issue_number} created: {issue['html_url']}"
        logger.info(
            f"Created issue #{issue_number} in {inputs.org}/{inputs.repo}",
            issue_number=issue_number,
            html_url=issue["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue created",
        )
