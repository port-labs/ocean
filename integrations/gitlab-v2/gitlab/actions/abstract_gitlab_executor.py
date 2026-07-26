from gitlab.clients.client_factory import create_gitlab_client
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.models import IntegrationRun

MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE = 20


class AbstractGitlabExecutor(AbstractExecutor):
    def __init__(self) -> None:
        self.client = create_gitlab_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        info = self.client.get_rate_limit_status()
        if not info:
            return False

        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        info = self.client.get_rate_limit_status()
        if not info:
            return 0

        return info.seconds_until_reset
