from abc import abstractmethod

from port_ocean.core.base import BaseWithContext
from port_ocean.models.port_app_config import PortAppConfig


class BasePortAppConfigWithContext(BaseWithContext):
    @abstractmethod
    async def get_port_app_config(self) -> PortAppConfig:
        pass
