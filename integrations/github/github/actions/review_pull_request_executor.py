import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import PullRequestActionError
from github.helpers.exceptions import InvalidActionParametersException


class ReviewPullRequestExecutor(AbstractGithubExecutor):
    ACTION_NAME = "review_pull_request"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        pr_number = run.execution_properties.get("prNumber")
        event = run.execution_properties.get("event")
        comment = run.execution_properties.get("body")

        if not (org and repo and pr_number and event):
            raise InvalidActionParametersException(
                "org, repo, prNumber, and event are required"
            )

        if event == "REQUEST_CHANGES" and not comment:
            raise InvalidActionParametersException(
                "body is required when event is REQUEST_CHANGES"
            )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Submitting {event} review on pull request #{pr_number} in {org}/{repo}",
            should_raise=False,
        )

        review_body: dict[str, str] = {"event": event}
        if comment:
            review_body["body"] = comment

        try:
            result = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/pulls/{pr_number}/reviews",
                method="POST",
                json_data=review_body,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise PullRequestActionError.from_response(
                e.response,
                f"Could not submit review on pull request #{pr_number} in {org}/{repo}",
            )
        except Exception as e:
            raise PullRequestActionError(
                f"Could not submit review on pull request #{pr_number} in {org}/{repo}: {e}"
            )

        logger.info(
            f"Submitted {event} review on pull request #{pr_number} in {org}/{repo}",
            pr_number=pr_number,
            review_id=result["id"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Review ({event}) submitted on pull request #{pr_number}: {result['html_url']}",
        )
