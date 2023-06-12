from abc import abstractmethod

from port_ocean.core.handlers.base import BaseHandler
from port_ocean.models.port_app_config import PortAppConfig


class BasePortAppConfigHandler(BaseHandler):
    @abstractmethod
    async def get_port_app_config(self) -> PortAppConfig:
        pass
