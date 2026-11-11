from port_ocean.context.ocean import ocean

from confluence.clients.client import ConfluenceClient


class ClientFactory:
    """Singleton factory for the Confluence Cloud client."""

    _instances: dict[type, ConfluenceClient] = {}

    @classmethod
    def get_client(cls) -> ConfluenceClient:
        if ConfluenceClient not in cls._instances:
            config = ocean.integration_config
            cls._instances[ConfluenceClient] = ConfluenceClient(
                site_url=config["confluence_host_url"],
                email=config["confluence_user_email"],
                api_token=config["confluence_api_token"],
            )
        return cls._instances[ConfluenceClient]

    @classmethod
    def clear(cls) -> None:
        cls._instances.clear()
