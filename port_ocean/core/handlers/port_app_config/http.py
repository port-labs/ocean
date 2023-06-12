from src.port_ocean.core.port_app_config.base import BasePortAppConfigHandler
from src.port_ocean.models.port_app_config import PortAppConfig


class HttpPortAppConfig(BasePortAppConfigHandler):
    async def get_port_app_config(self) -> PortAppConfig:
        pass
