from github.clients.client_factory import create_github_client_for_org
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.models import IntegrationRun

MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW = 20


class AbstractGithubExecutor(AbstractExecutor):
    async def get_rest_client(self, organization: str) -> GithubRestClient:
        return await create_github_client_for_org(organization)

    async def _get_rate_limit_client(
        self, run: IntegrationRun
    ) -> GithubRestClient | None:
        organization = run.execution_properties.get("org")
        if not isinstance(organization, str):
            return None
        return await self.get_rest_client(organization)

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        client = await self._get_rate_limit_client(run)
        info = client.get_rate_limit_status() if client else None
        if not info:
            return False

        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        client = await self._get_rate_limit_client(run)
        info = client.get_rate_limit_status() if client else None
        if not info:
            return 0

        return info.seconds_until_reset
