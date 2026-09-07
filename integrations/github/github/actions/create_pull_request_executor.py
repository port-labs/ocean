import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import CreatePullRequestError
from github.clients.client_factory import create_github_client_for_org
from github.clients.http.base_client import AbstractGithubClient
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException

CREATING_STATUS_LABEL = "Creating PR"
CREATED_STATUS_LABEL = "PR created"


class CreatePullRequestExecutor(AbstractGithubExecutor):
    ACTION_NAME = "create_pull_request"
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
        title = run.execution_properties.get("title")
        head = run.execution_properties.get("head")
        base = run.execution_properties.get("base")

        if not (org and repo and title and head and base):
            raise InvalidActionParametersException(
                "org, repo, title, head, and base are required"
            )

        rest_client = (await self._get_execution_clients(run))[0]
        if not isinstance(rest_client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")

        await ocean.port_client.post_run_log(
            run,
            f"Creating pull request '{title}' in {org}/{repo} ({head} → {base})",
            should_raise=False,
        )

        body: dict[str, str | bool] = {
            "title": title,
            "head": head,
            "base": base,
        }
        pr_body = run.execution_properties.get("body")
        if pr_body:
            body["body"] = pr_body
        draft = run.execution_properties.get("draft")
        if draft is not None:
            body["draft"] = draft

        try:
            pr = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/pulls",
                method="POST",
                json_data=body,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise CreatePullRequestError.from_response(
                e.response, f"Could not create pull request in {org}/{repo}"
            )

        if not pr or "number" not in pr or "html_url" not in pr:
            logger.warning(
                f"Received empty or incomplete response from GitHub for pull request creation in {org}/{repo}",
                org=org,
                repo=repo,
            )
            raise CreatePullRequestError(
                "Failed to create pull request: upstream returned an empty or incomplete response"
            )

        logger.info(
            f"Created PR #{pr['number']} in {org}/{repo}",
            pr_number=pr["number"],
            html_url=pr["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Pull request #{pr['number']} created: {pr['html_url']}",
        )
