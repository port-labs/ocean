from github.clients.client_factory import create_github_client_for_org
from github.clients.http.base_client import AbstractGithubClient
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.models import IntegrationRun

MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS = 20


class AbstractGithubExecutor(AbstractExecutor):
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

    def _is_client_close_to_rate_limit(self, client: AbstractGithubClient) -> bool:
        info = client.get_rate_limit_status()
        if not info:
            return False

        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS

    def _get_client_seconds_until_rate_limit(
        self, client: AbstractGithubClient
    ) -> float:
        info = client.get_rate_limit_status()
        if not info:
            return 0.0

        return info.seconds_until_reset

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        clients = await self._get_execution_clients(run)
        if not clients:
            return False

        return any(self._is_client_close_to_rate_limit(client) for client in clients)

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        clients = await self._get_execution_clients(run)
        if not clients:
            return 0.0

        return max(
            self._get_client_seconds_until_rate_limit(client) for client in clients
        )
