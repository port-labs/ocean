from loguru import logger
from port_ocean.context.ocean import ocean

from incident_io.clients.client import IncidentIoClient
from incident_io.helpers.utils import resolve_api_base_url


class ClientFactory:
    """Singleton factory for the incident.io client."""

    _instances: dict[type, IncidentIoClient] = {}

    @classmethod
    def get_client(cls) -> IncidentIoClient:
        if IncidentIoClient not in cls._instances:
            config = ocean.integration_config
            base_url = resolve_api_base_url(config.get("incident_io_api_url"))
            api_key = config.get("incident_io_api_key")
            if not isinstance(api_key, str) or not api_key.strip():
                raise ValueError("incidentIoApiKey is required.")
            cls._instances[IncidentIoClient] = IncidentIoClient(
                base_url=base_url,
                api_key=api_key.strip(),
            )
            logger.info(f"Created incident.io client for {base_url}")
        return cls._instances[IncidentIoClient]

    @classmethod
    def clear(cls) -> None:
        cls._instances.clear()
