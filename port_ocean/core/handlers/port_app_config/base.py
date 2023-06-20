from abc import abstractmethod

from port_ocean.core.base import BaseWithContext
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class BasePortAppConfig(BaseWithContext):
    @abstractmethod
    async def get_port_app_config(self) -> PortAppConfig:
        pass
