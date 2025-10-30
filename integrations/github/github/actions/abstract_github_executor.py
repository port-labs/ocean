from github.clients.client_factory import create_github_client
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor


MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW = 20


class AbstractGithubExecutor(AbstractExecutor):
    def __init__(self):
        self.rest_client = create_github_client()

    async def is_close_to_rate_limit(self) -> bool:
        info = self.rest_client.get_rate_limit_status()
        if not info:
            return False

        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW

    async def get_remaining_seconds_until_rate_limit(self) -> float:
        info = self.rest_client.get_rate_limit_status()
        if not info:
            return 0

        return info.seconds_until_reset
