from abc import abstractmethod
from typing import Type, Any

from port_ocean.context.event import event
from port_ocean.core.base import BaseWithContext
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class BasePortAppConfig(BaseWithContext):
    CONFIG_CLASS: Type[PortAppConfig] = PortAppConfig

    @abstractmethod
    async def _get_port_app_config(self) -> dict[str, Any]:
        pass

    async def get_port_app_config(self) -> PortAppConfig:
        raw_config = await self._get_port_app_config()
        config = self.CONFIG_CLASS.parse_obj(raw_config)
        event.port_app_config = config
        return config
