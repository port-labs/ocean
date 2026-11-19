from typing import Any

from port_ocean.context.ocean import ocean

from factory_ai.clients.factory_client import FactoryClient
from factory_ai.config import DEFAULT_FACTORY_API_HOST


class ClientFactory:
    """Singleton factory for the Factory.ai HTTP client."""

    _client: FactoryClient | None = None

    @classmethod
    def get_client(cls) -> FactoryClient:
        if cls._client is not None:
            return cls._client

        integration_config: dict[str, Any] = ocean.integration_config
        cls._client = FactoryClient(
            api_host=integration_config.get(
                "factory_api_host", DEFAULT_FACTORY_API_HOST
            ),
            api_key=integration_config["factory_api_key"],
            request_timeout_seconds=ocean.config.client_timeout,
        )
        return cls._client
