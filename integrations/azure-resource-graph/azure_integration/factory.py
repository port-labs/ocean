from port_ocean.context.ocean import ocean
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import ClientSecretCredential
from azure_integration.clients.base import AbstractAzureClient
from enum import StrEnum
from loguru import logger
from typing import Dict, Type
from azure_integration.clients.rest.resource_management_client import (
    AzureResourceManagerClient,
)
from azure_integration.clients.rest.resource_graph_client import (
    AzureResourceGraphClient,
)
from azure_integration.helpers.exceptions import MissingAzureCredentials
from azure_integration.helpers.rate_limiter import (
    AdaptiveTokenBucketRateLimiter,
    AZURERM_BUCKET_REFILL_RATE,
    AZURERM_RATELIMIT_CAPACITY,
)


class AzureClientType(StrEnum):
    RESOURCE_MANAGER = "resource_manager"
    RESOURCE_GRAPH = "resource_graph"


class AzureClientFactory:
    _instance = None
    _clients: Dict[AzureClientType, Type[AbstractAzureClient]] = {
        AzureClientType.RESOURCE_MANAGER: AzureResourceManagerClient,
        AzureClientType.RESOURCE_GRAPH: AzureResourceGraphClient,
    }
    _instances: Dict[AzureClientType, AbstractAzureClient] = {}

    def __new__(cls) -> "AzureClientFactory":
        if cls._instance is None:
            cls._instance = super(AzureClientFactory, cls).__new__(cls)
        return cls._instance

    def get_client(self, client_type: AzureClientType) -> AbstractAzureClient:
        """
        Get or create AzureClient instances from Ocean configuration.

        Returns:
            AbstractAzureClient
        """
        logger.info(f"Getting Azure {client_type.value} client")
        if client_type not in self._instances:
            if client_type not in AzureClientType:
                raise ValueError(f"Invalid client type: {client_type}")

            base_url = ocean.integration_config["azure_base_url"]
            credential = AzureAuthenticatorFactory.create(
                tenant_id=ocean.integration_config["azure_tenant_id"],
                client_id=ocean.integration_config["azure_client_id"],
                client_secret=ocean.integration_config["azure_client_secret"],
            )
            rate_limiter = AdaptiveTokenBucketRateLimiter(
                capacity=AZURERM_RATELIMIT_CAPACITY,
                refill_rate=AZURERM_BUCKET_REFILL_RATE,
            )
            self._instances[client_type] = self._clients[client_type](
                credential=credential, base_url=base_url, rate_limiter=rate_limiter
            )
            logger.info(f"Created new Azure {client_type} client")
        return self._instances[client_type]


class AzureAuthenticatorFactory:
    @staticmethod
    def create(
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> AsyncTokenCredential:
        if not (tenant_id and client_id and client_secret):
            raise MissingAzureCredentials(
                "Missing Azure credentials: tenant_id, client_id, and client_secret are required."
            )

        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )


def create_azure_client(
    client_type: AzureClientType = AzureClientType.RESOURCE_MANAGER,
) -> AbstractAzureClient:
    factory = AzureClientFactory()
    return factory.get_client(client_type)
