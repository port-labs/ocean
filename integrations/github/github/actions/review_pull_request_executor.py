import httpx
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import ReviewPullRequestError
from github.helpers.exceptions import InvalidActionParametersException


class ReviewPullRequestInputs(AbstractGithubActionInput):
    org: str
    repo: str
    prNumber: int
    event: str
    body: str | None = None


class ReviewPullRequestExecutor(AbstractGithubExecutor):
    ACTION_NAME = "review_pull_request"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = ReviewPullRequestInputs.from_execution_properties(
            run.execution_properties
        )

        if inputs.event == "REQUEST_CHANGES" and not inputs.body:
            raise InvalidActionParametersException(
                "body is required when event is REQUEST_CHANGES"
            )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Submitting {inputs.event} review on pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            status_label="Submitting review",
            should_raise=False,
        )

        review_body: dict[str, str] = {"event": inputs.event}
        if inputs.body:
            review_body["body"] = inputs.body

        try:
            result = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/pulls/{inputs.prNumber}/reviews",
                method="POST",
                json_data=review_body,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise ReviewPullRequestError.from_response(
                e.response,
                f"Could not submit review on pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            )

        review_id = result.get("id")
        if review_id is None:
            raise ReviewPullRequestError(
                "Failed to submit review: GitHub returned an empty or incomplete response"
            )

        logger.info(
            f"Submitted {inputs.event} review on pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            pr_number=inputs.prNumber,
            review_id=review_id,
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Review ({inputs.event}) submitted on pull request #{inputs.prNumber}: {result['html_url']}",
            status_label="Review submitted",
        )
