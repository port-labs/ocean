from abc import abstractmethod
from github.clients.http.base_client import AbstractGithubClient
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.models import IntegrationRun

MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW = 20


class AbstractGithubExecutor(AbstractExecutor):
    @abstractmethod
    async def _get_execution_client(self, run: IntegrationRun) -> AbstractGithubClient:
        pass

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        client = await self._get_execution_client(run)
        info = client.get_rate_limit_status()
        if not info:
            return False

        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        client = await self._get_execution_client(run)
        info = client.get_rate_limit_status()
        if not info:
            return 0

        return info.seconds_until_reset
