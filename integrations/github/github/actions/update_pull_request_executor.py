import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import UpdatePullRequestError
from github.clients.client_factory import create_github_client_for_org
from github.clients.http.base_client import AbstractGithubClient
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException



class UpdatePullRequestExecutor(AbstractGithubExecutor):
    ACTION_NAME = "update_pull_request"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_execution_clients(
        self, run: IntegrationRun
    ) -> list[AbstractGithubClient]:
        organization = run.execution_properties.get("org")
        if not isinstance(organization, str):
            raise InvalidActionParametersException("org is required")
        return [await create_github_client_for_org(organization)]

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        if not org or not repo:
            return None
        return f"{org}/{repo}"

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        pr_number = run.execution_properties.get("prNumber")

        if not (org and repo and pr_number):
            raise InvalidActionParametersException(
                "org, repo, and prNumber are required"
            )

        patch_body: dict[str, str] = {}
        for key in ("title", "body", "state", "base"):
            value = run.execution_properties.get(key)
            if value is not None:
                patch_body[key] = value

        if not patch_body:
            raise InvalidActionParametersException(
                "At least one field to update is required (title, body, state, or base)"
            )

        rest_client = (await self._get_execution_clients(run))[0]
        if not isinstance(rest_client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")

        await ocean.port_client.post_run_log(
            run,
            f"Updating pull request #{pr_number} in {org}/{repo}",
            should_raise=False,
        )

        try:
            pr = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/pulls/{pr_number}",
                method="PATCH",
                json_data=patch_body,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise UpdatePullRequestError.from_response(
                e.response, f"Could not update PR #{pr_number} in {org}/{repo}"
            )

        if not pr or "number" not in pr or "html_url" not in pr:
            logger.warning(
                f"Received empty or incomplete response from GitHub for pull request update in {org}/{repo}",
                org=org,
                repo=repo,
                pr_number=pr_number,
            )
            raise UpdatePullRequestError(
                "Failed to update pull request: upstream returned an empty or incomplete response"
            )

        logger.info(
            f"Updated PR #{pr['number']} in {org}/{repo}",
            pr_number=pr["number"],
            html_url=pr["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Pull request #{pr['number']} updated: {pr['html_url']}",
        )
