from typing import Optional

from loguru import logger

from azure_devops.actions.exceptions import MultipleOrganizationsNotSupportedError
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.models import IntegrationRun


class AbstractAzureDevopsExecutor(AbstractExecutor):
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
