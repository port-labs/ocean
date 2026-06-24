from github.clients.client_factory import create_github_client_for_org
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor


MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW = 20


class AbstractGithubExecutor(AbstractExecutor):
    def get_rest_client(self, organization: str | None = None) -> GithubRestClient:
        return create_github_client_for_org(organization)

    async def is_close_to_rate_limit(self, organization: str | None = None) -> bool:
        info = self.get_rest_client(organization).get_rate_limit_status()
        if not info:
            return False

        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW

    async def get_remaining_seconds_until_rate_limit(
        self, organization: str | None = None
    ) -> float:
        info = self.get_rest_client(organization).get_rate_limit_status()
        if not info:
            return 0

        return info.seconds_until_reset
