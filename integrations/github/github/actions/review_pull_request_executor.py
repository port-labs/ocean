import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_pull_request_executor import AbstractPullRequestExecutor
from github.actions.exceptions import ReviewPullRequestError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException

# https://docs.github.com/en/rest/pulls/reviews#create-a-review-for-a-pull-request
VALID_REVIEW_EVENTS = frozenset({"APPROVE", "REQUEST_CHANGES", "COMMENT"})


class ReviewPullRequestExecutor(AbstractPullRequestExecutor):
    ACTION_NAME = "review_pull_request"

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        pr_number = run.execution_properties.get("prNumber")
        event = run.execution_properties.get("event")

        if not (org and repo and pr_number and event):
            raise InvalidActionParametersException(
                "org, repo, prNumber, and event are required"
            )

        if event not in VALID_REVIEW_EVENTS:
            raise InvalidActionParametersException(
                f"event must be one of: {', '.join(sorted(VALID_REVIEW_EVENTS))}"
            )

        if event == "REQUEST_CHANGES":
            body = run.execution_properties.get("body")
            if not body:
                raise InvalidActionParametersException(
                    "body is required when event is REQUEST_CHANGES"
                )

        rest_client = (await self._get_execution_clients(run))[0]
        if not isinstance(rest_client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")

        await ocean.port_client.post_run_log(
            run,
            f"Submitting {event} review on pull request #{pr_number} in {org}/{repo}",
            should_raise=False,
        )

        review_body: dict[str, str] = {"event": event}
        body = run.execution_properties.get("body")
        if body:
            review_body["body"] = body

        try:
            result = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/pulls/{pr_number}/reviews",
                method="POST",
                json_data=review_body,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise ReviewPullRequestError.from_response(
                e.response,
                f"Could not submit review on pull request #{pr_number} in {org}/{repo}",
            )

        if not result or "id" not in result:
            logger.warning(
                f"Received empty or incomplete response from GitHub for pull request review in {org}/{repo}",
                org=org,
                repo=repo,
                pr_number=pr_number,
            )
            raise ReviewPullRequestError(
                "Failed to submit review: upstream returned an empty or incomplete response"
            )

        logger.info(
            f"Submitted {event} review on pull request #{pr_number} in {org}/{repo}",
            pr_number=pr_number,
            review_id=result["id"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Review ({event}) submitted on pull request #{pr_number}: {result.get('html_url', '')}",
        )
