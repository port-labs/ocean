from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Optional

from loguru import logger

from azure_devops.actions.exceptions import MultipleOrganizationsNotSupportedError
from azure_devops.client.auth import BearerAuthProvider
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun


async def _resolve_user_token(run: IntegrationRun) -> str | None:
    from port_ocean.identity_propagation.token_exchanger import resolve_user_token

    return await resolve_user_token(run)


class AbstractAzureDevopsExecutor(AbstractExecutor):
    # `AbstractExecutor` declares this as an annotation only, so executors that
    # complete synchronously rely on this default when `register_executor` reads
    # it. The explicit type keeps mypy happy when a subclass overrides it with a
    # processor class.
    WEBHOOK_PROCESSOR_CLASS: Optional[type[AbstractWebhookProcessor]] = None

    def __init__(self) -> None:
        self._client: Optional[AzureDevopsClient] = None

    @property
    def client(self) -> AzureDevopsClient:
        """Resolve the single configured Azure DevOps client lazily.

        Actions currently support Single Account mode only. The client is built
        on first use (not at registration time) so the integration still starts
        when actions are disabled or multiple organizations are configured.
        """
        if self._client is None:
            manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
            clients = manager.get_clients()
            if len(clients) != 1:
                logger.error(
                    "Azure DevOps actions currently support a single organization "
                    f"(Single Account mode); found {len(clients)} configured clients.",
                    configured_clients=len(clients),
                )
                raise MultipleOrganizationsNotSupportedError(
                    "Azure DevOps actions currently support a single organization "
                    f"(Single Account mode); found {len(clients)} configured clients."
                )
            self._client = clients[0]
        return self._client

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return self.client.is_close_to_rate_limit()

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return self.client.seconds_until_rate_limit_reset()

    def _client_for_token(self, token: str) -> AzureDevopsClient:
        base_client = self.client
        return AzureDevopsClient(
            base_client._organization_base_url,
            BearerAuthProvider(token),
            base_client.webhook_auth_username,
            base_client.excluded_tags,
        )

    @asynccontextmanager
    async def _api_client_for_run(
        self, run: IntegrationRun
    ) -> AsyncIterator[AzureDevopsClient]:
        user_token = await _resolve_user_token(run)
        if user_token:
            api_client = self._client_for_token(user_token)
            try:
                yield api_client
            finally:
                await api_client.aclose()
        else:
            yield self.client
