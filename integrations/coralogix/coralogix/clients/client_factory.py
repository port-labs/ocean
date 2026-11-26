from loguru import logger
from port_ocean.context.ocean import ocean

from coralogix.clients.client import CoralogixClient
from coralogix.helpers.utils import resolve_api_base_url


class ClientFactory:
    """Singleton factory for the Coralogix client."""

    _instances: dict[type, CoralogixClient] = {}

    @classmethod
    def get_client(cls) -> CoralogixClient:
        if CoralogixClient not in cls._instances:
            config = ocean.integration_config
            base_url = resolve_api_base_url(config["coralogix_api_url"])
            cls._instances[CoralogixClient] = CoralogixClient(
                base_url=base_url,
                api_key=config["coralogix_api_key"],
            )
            logger.info(f"Created Coralogix client for {base_url}")
        return cls._instances[CoralogixClient]

    @classmethod
    def clear(cls) -> None:
        cls._instances.clear()
