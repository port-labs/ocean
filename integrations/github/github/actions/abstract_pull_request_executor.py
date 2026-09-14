from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.clients.client_factory import create_github_client_for_org
from github.clients.http.base_client import AbstractGithubClient
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import IntegrationRun


class AbstractPullRequestExecutor(AbstractGithubExecutor):
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_execution_clients(
        self, run: IntegrationRun
    ) -> list[AbstractGithubClient]:
        organization = run.execution_properties.get("org")
        if not isinstance(organization, str):
            raise InvalidActionParametersException("org is required")
        return [await create_github_client_for_org(organization)]

    async def _get_rest_client(self, run: IntegrationRun) -> GithubRestClient:
        client = (await self._get_execution_clients(run))[0]
        if not isinstance(client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")
        return client

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        if not isinstance(org, str) or not isinstance(repo, str):
            return None
        return f"{org}/{repo}"
