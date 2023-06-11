from abc import abstractmethod

from port_ocean.config.integration import IntegrationConfiguration
from port_ocean.models.port_app_config import PortAppConfig


class BasePortAppConfigHandler:
    def __init__(self, config: IntegrationConfiguration):
        self.config = config

    @abstractmethod
    async def get_port_app_config(self) -> PortAppConfig:
        pass
