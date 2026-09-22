from typing import Any

import httpx
from loguru import logger
from pydantic import model_validator

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import UpdatePullRequestError


class UpdatePullRequestInputs(AbstractGithubActionInput):
    org: str
    repo: str
    prNumber: int
    title: str | None = None
    body: str | None = None
    base: str | None = None

    @model_validator(mode="after")
    def check_at_least_one_update_field(self) -> "UpdatePullRequestInputs":
        if not any(
            [
                self.title is not None,
                self.body is not None,
                self.base is not None,
            ]
        ):
            raise ValueError(
                "At least one field to update is required (title, body, or base)"
            )
        return self

    def to_api_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.title is not None:
            payload["title"] = self.title
        if self.body is not None:
            payload["body"] = self.body
        if self.base is not None:
            payload["base"] = self.base
        return payload


class UpdatePullRequestExecutor(AbstractGithubExecutor):
    ACTION_NAME = "update_pull_request"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = UpdatePullRequestInputs.from_execution_properties(
            run.execution_properties
        )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Updating pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            status_label="Updating pull request",
            should_raise=False,
        )

        try:
            pr = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/pulls/{inputs.prNumber}",
                method="PATCH",
                json_data=inputs.to_api_payload(),
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise UpdatePullRequestError.from_response(
                e.response,
                f"Could not update pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            )

        pr_number = pr.get("number")
        if pr_number is None:
            raise UpdatePullRequestError(
                "Failed to update pull request: GitHub returned an empty or incomplete response"
            )

        message = f"Pull request #{pr_number} updated: {pr['html_url']}"
        logger.info(
            f"Updated pull request #{pr_number} in {inputs.org}/{inputs.repo}",
            pr_number=pr_number,
            html_url=pr["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Pull request updated",
        )
