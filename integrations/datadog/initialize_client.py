from client import DatadogClient
from client_manager import DatadogClientManager


def init_client() -> DatadogClient:
    return DatadogClientManager.create_from_ocean_config().get_default_client()


def init_client_for_org(org_id: str) -> DatadogClient:
    """Return the client for a specific org, falling back to the default client."""
    if not org_id:
        return init_client()

    manager = DatadogClientManager.create_from_ocean_config()
    client = manager.get_client_for_org(org_id)
    if client:
        return client

    return manager.get_default_client()
