from typing import Any

import httpx
from loguru import logger

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.utils import extract_error_message
from github.clients.client_factory import create_github_client_for_org
from github.clients.http.base_client import AbstractGithubClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError


class CreateIssueExecutor(AbstractGithubExecutor):
    ACTION_NAME = "create_issue"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        if not isinstance(org, str) or not isinstance(repo, str):
            return None
        return f"{org}/{repo}"

    async def _get_execution_clients(
        self, run: IntegrationRun
    ) -> list[AbstractGithubClient]:
        organization = run.execution_properties.get("org")
        if not isinstance(organization, str):
            raise InvalidActionParametersException("org is required")
        return [await create_github_client_for_org(organization)]

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        title = run.execution_properties.get("title")

        if not (isinstance(org, str) and org):
            raise InvalidActionParametersException("org is required")
        if not (isinstance(repo, str) and repo):
            raise InvalidActionParametersException("repo is required")
        if not (isinstance(title, str) and title):
            raise InvalidActionParametersException("title is required")

        await ocean.port_client.post_run_log(
            run,
            f"Creating GitHub issue in {org}/{repo}",
            status_label="Creating issue",
            should_raise=False,
        )

        try:
            rest_client = await create_github_client_for_org(org)
            response = await rest_client.make_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/issues",
                method="POST",
                json_data={"title": title},
                ignore_default_errors=False,
            )
            created_issue: dict[str, Any] = response.json()
        except httpx.HTTPStatusError as error:
            raise ActionExecutionError(
                f"Could not create issue in '{org}/{repo}': {extract_error_message(error.response)}"
            ) from error
        except Exception as error:
            raise ActionExecutionError(
                f"Could not create issue in '{org}/{repo}': {error}"
            ) from error

        issue_number = created_issue.get("number")
        issue_html_url = created_issue.get("html_url")
        if issue_number is None:
            raise ActionExecutionError(
                "Failed to create issue: GitHub returned an empty or incomplete response"
            )

        message = f"Created issue #{issue_number}"
        if isinstance(issue_html_url, str) and issue_html_url:
            message = f"{message}: {issue_html_url}"

        await ocean.port_client.post_run_log(
            run,
            message,
            should_raise=False,
        )
        logger.info(
            "Created GitHub issue",
            org=org,
            repo=repo,
            issue_number=issue_number,
        )

        if isinstance(run, WorkflowNodeRun):
            run.output = {
                "issueNumber": issue_number,
                "issueId": str(created_issue.get("id", "")),
                "issueUrl": issue_html_url if isinstance(issue_html_url, str) else "",
            }

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue created",
        )
