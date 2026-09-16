from typing import Any

import httpx
from loguru import logger
from pydantic import Field

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import CreatePullRequestError


class CreatePullRequestInputs(AbstractGithubActionInput):
    org: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    title: str = Field(min_length=1)
    head: str = Field(min_length=1)
    base: str = Field(min_length=1)
    body: str | None = None
    draft: bool | None = None

    def to_api_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": self.title,
            "head": self.head,
            "base": self.base,
        }
        if self.body is not None:
            payload["body"] = self.body
        if self.draft is not None:
            payload["draft"] = self.draft
        return payload


class CreatePullRequestExecutor(AbstractGithubExecutor):
    ACTION_NAME = "create_pull_request"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreatePullRequestInputs.from_execution_properties(
            run.execution_properties
        )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Creating pull request '{inputs.title}' in {inputs.org}/{inputs.repo} ({inputs.head} → {inputs.base})",
            status_label="Creating pull request",
            should_raise=False,
        )

        try:
            pr = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/pulls",
                method="POST",
                json_data=inputs.to_api_payload(),
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise CreatePullRequestError.from_response(
                e.response,
                f"Could not create pull request in {inputs.org}/{inputs.repo}",
            )

        pr_number = pr.get("number")
        if pr_number is None:
            raise CreatePullRequestError(
                "Failed to create pull request: GitHub returned an empty or incomplete response"
            )

        message = f"Pull request #{pr_number} created: {pr['html_url']}"
        logger.info(
            f"Created pull request #{pr_number} in {inputs.org}/{inputs.repo}",
            pr_number=pr_number,
            html_url=pr["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Pull request created",
        )
