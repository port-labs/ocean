from abc import abstractmethod

from github.clients.http.base_client import AbstractGithubClient
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.models import IntegrationRun

MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW = 20


class AbstractGithubExecutor(AbstractExecutor):
    @abstractmethod
    async def _get_execution_clients(
        self, run: IntegrationRun
    ) -> list[AbstractGithubClient]:
        pass

    def _is_client_close_to_rate_limit(self, client: AbstractGithubClient) -> bool:
        info = client.get_rate_limit_status()
        if not info:
            return False

        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW

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
