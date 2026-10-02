from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from gitlab.clients.client_factory import create_gitlab_client
from gitlab.clients.gitlab_client import GitLabClient
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.identity_propagation.token_exchanger import resolve_user_token
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE = 20


class AbstractGitlabExecutor(AbstractExecutor):
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

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

    @asynccontextmanager
    async def _api_client_for_run(
        self, run: IntegrationRun
    ) -> AsyncIterator[GitLabClient]:
        user_token = await resolve_user_token(run)
        if user_token:
            host = str(ocean.integration_config["gitlab_host"]).rstrip("/")
            api_client = GitLabClient(host, user_token)

            # Do not fall back to the integration OAuth token on 401 — that would
            # execute the action as the integration instead of the user.
            api_client.rest._auth_client.disable_token_refresh()
            try:
                yield api_client
            finally:
                await api_client.rest._client.aclose()
        else:
            yield self.client
