from typing import Any, Dict, Type

from loguru import logger

from port_ocean.core.handlers.port_app_config.base import BasePortAppConfigWithContext
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class APIPortAppConfig(BasePortAppConfigWithContext):
    CONFIG_CLASS: Type[PortAppConfig] = PortAppConfig

    async def _get_port_app_config(self) -> Dict[str, Any]:
        logger.info("Fetching port app config")
        return await self.context.port_client.get_integration(
            self.context.config.integration.identifier
        )

    async def get_port_app_config(self) -> PortAppConfig:
        integration = await self._get_port_app_config()
        return self.CONFIG_CLASS.parse_obj(integration["config"])
