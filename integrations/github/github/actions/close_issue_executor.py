from typing import Any, Literal

import httpx
from loguru import logger
from pydantic import model_validator

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import CloseIssueError


class CloseIssueInputs(AbstractGithubActionInput):
    org: str
    repo: str
    issueNumber: int
    stateReason: Literal["completed", "not_planned", "duplicate"] = "completed"
    duplicateIssueId: int | None = None

    @model_validator(mode="after")
    def check_duplicate_requires_issue_id(self) -> "CloseIssueInputs":
        if self.stateReason == "duplicate" and self.duplicateIssueId is None:
            raise ValueError(
                "duplicateIssueId is required when stateReason is 'duplicate'"
            )
        return self

    def to_api_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "state": "closed",
            "state_reason": self.stateReason,
        }
        if self.stateReason == "duplicate" and self.duplicateIssueId is not None:
            payload["duplicate_issue_id"] = self.duplicateIssueId
        return payload


class CloseIssueExecutor(AbstractGithubExecutor):
    ACTION_NAME = "close_issue"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CloseIssueInputs.from_execution_properties(run.execution_properties)

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Closing issue #{inputs.issueNumber} in {inputs.org}/{inputs.repo} as {inputs.stateReason}",
            status_label="Closing issue",
            should_raise=False,
        )

        try:
            issue = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/issues/{inputs.issueNumber}",
                method="PATCH",
                json_data=inputs.to_api_payload(),
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise CloseIssueError.from_response(
                e.response,
                f"Could not close issue #{inputs.issueNumber} in {inputs.org}/{inputs.repo}",
            )

        issue_number = issue.get("number")
        if issue_number is None:
            raise CloseIssueError(
                "Failed to close issue: GitHub returned an empty or incomplete response"
            )

        message = f"Issue #{issue_number} closed: {issue['html_url']}"
        logger.info(
            f"Closed issue #{issue_number} in {inputs.org}/{inputs.repo}",
            issue_number=issue_number,
            html_url=issue["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue closed",
        )
